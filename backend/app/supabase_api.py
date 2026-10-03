from typing import Any

import httpx
import jwt
from fastapi import HTTPException, status

from .config import settings


class SupabaseError(RuntimeError):
    pass


def _detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or f"HTTP {response.status_code}"
    if isinstance(payload, dict):
        for key in ("msg", "error_description", "error", "message"):
            value = payload.get(key)
            if value:
                return str(value)
    return f"HTTP {response.status_code}"


class SupabaseAuth:
    def __init__(self) -> None:
        self.base_url = settings.supabase_auth_url
        self.timeout = settings.supabase_timeout
        self._jwks_client: jwt.PyJWKClient | None = None

    @property
    def configured(self) -> bool:
        return bool(settings.supabase_url and settings.supabase_service_key)

    def _service_headers(self) -> dict[str, str]:
        key = settings.supabase_service_key or settings.supabase_anon_key
        return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _public_headers(self) -> dict[str, str]:
        key = settings.supabase_anon_key or settings.supabase_service_key
        return {"apikey": key, "Content-Type": "application/json"}

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        if not settings.supabase_url:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "SUPABASE_URL is not configured on the server.",
            )
        url = f"{self.base_url}{path}"
        try:
            return httpx.request(
                method,
                url,
                json=json_body,
                headers=headers or self._public_headers(),
                params=params,
                timeout=self.timeout,
            )
        except httpx.HTTPError as error:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "The sign-in service is unreachable. Please try again.",
            ) from error

    def sign_in(self, email: str, password: str) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/token",
            params={"grant_type": "password"},
            json_body={"email": email, "password": password},
        )
        if response.status_code >= 400:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
        return response.json()

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/token",
            params={"grant_type": "refresh_token"},
            json_body={"refresh_token": refresh_token},
        )
        if response.status_code >= 400:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Please log in again.")
        return response.json()

    def sign_out(self, access_token: str) -> None:
        self._request("POST", "/logout", headers={**self._public_headers(), "Authorization": f"Bearer {access_token}"})

    def create_user(self, email: str, password: str, full_name: str) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/admin/users",
            headers=self._service_headers(),
            json_body={
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"full_name": full_name},
            },
        )
        if response.status_code >= 400:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, _detail(response))
        return response.json()

    def delete_user(self, auth_user_id: str) -> None:
        self._request("DELETE", f"/admin/users/{auth_user_id}", headers=self._service_headers())

    def update_password(self, auth_user_id: str, password: str) -> None:
        response = self._request(
            "PUT",
            f"/admin/users/{auth_user_id}",
            headers=self._service_headers(),
            json_body={"password": password},
        )
        if response.status_code >= 400:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, _detail(response))

    def update_own_password(self, access_token: str, password: str) -> None:
        response = self._request(
            "PUT",
            "/user",
            headers={**self._public_headers(), "Authorization": f"Bearer {access_token}"},
            json_body={"password": password},
        )
        if response.status_code >= 400:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, _detail(response))

    def send_recovery_email(self, email: str, redirect_to: str) -> None:
        self._request("POST", "/recover", json_body={"email": email, "redirect_to": redirect_to})

    def fetch_user(self, access_token: str) -> dict[str, Any] | None:
        response = self._request(
            "GET",
            "/user",
            headers={**self._public_headers(), "Authorization": f"Bearer {access_token}"},
        )
        if response.status_code >= 400:
            return None
        payload = response.json()
        return payload if isinstance(payload, dict) else None

    def _jwks(self) -> jwt.PyJWKClient:
        if self._jwks_client is None:
            self._jwks_client = jwt.PyJWKClient(settings.supabase_jwks_url, cache_keys=True, lifespan=600)
        return self._jwks_client

    def verify_access_token(self, token: str) -> dict[str, Any] | None:
        audience = "authenticated"
        issuer = settings.supabase_auth_url

        if settings.supabase_jwt_secret:
            try:
                claims = jwt.decode(
                    token,
                    settings.supabase_jwt_secret,
                    algorithms=["HS256"],
                    audience=audience,
                    issuer=issuer,
                    options={"verify_aud": False},
                )
                return self._checked(claims)
            except jwt.PyJWTError:
                pass

        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg", "")
            if algorithm and algorithm != "HS256":
                signing_key = self._jwks().get_signing_key_from_jwt(token)
                claims = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=[algorithm],
                    audience=audience,
                    issuer=issuer,
                    options={"verify_aud": False},
                )
                return self._checked(claims)
        except jwt.PyJWTError:
            pass
        except Exception:
            pass

        fetched = self.fetch_user(token)
        if not fetched:
            return None
        return self._checked(
            {
                "sub": fetched.get("id"),
                "email": fetched.get("email"),
                "role": fetched.get("role"),
            }
        )

    @staticmethod
    def _checked(claims: dict[str, Any]) -> dict[str, Any] | None:
        if not claims.get("sub"):
            return None
        return claims
