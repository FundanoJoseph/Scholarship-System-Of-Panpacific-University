"""A small stand-in for Supabase Auth + Storage.

It implements the endpoints this backend calls, with the same request and
response shapes, so AUTH_PROVIDER=supabase and STORAGE_BACKEND=supabase can be
exercised locally (see scripts/verify_supabase_mode.py):

    python -m uvicorn mock_supabase:app --port 8020      # from backend/scripts

MOCK_SIGNING=rs256 (default) serves a JWKS endpoint like a new Supabase project;
MOCK_SIGNING=hs256 signs with a shared secret like a legacy project.

    /auth/v1/admin/users            (service key)  create / update / delete
    /auth/v1/token?grant_type=...   (anon key)     password + refresh grants
    /auth/v1/user                   (anon key)     fetch / update own password
    /auth/v1/logout, /auth/v1/recover
    /auth/v1/.well-known/jwks.json                 RS256 public keys
    /storage/v1/object/{bucket}/{path}             upload / download / delete
"""

import json
import os
import secrets
import time
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Body, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from jwt.algorithms import RSAAlgorithm

SIGNING_MODE = os.environ.get("MOCK_SIGNING", "rs256")
SHARED_SECRET = os.environ.get("MOCK_SHARED_SECRET", "mock-supabase-shared-secret-value")
ANON_KEY = "anon-key-for-tests"
SERVICE_KEY = "service-key-for-tests"

PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_JWK = json.loads(RSAAlgorithm.to_jwk(PRIVATE_KEY.public_key()))
PUBLIC_JWK.update({"kid": "mock-key-1", "alg": "RS256", "use": "sig"})

SECRET = SHARED_SECRET if SIGNING_MODE == "hs256" else PRIVATE_KEY

app = FastAPI(title="Mock Supabase")

users: dict[str, dict[str, Any]] = {}
refresh_tokens: dict[str, str] = {}
objects: dict[str, bytes] = {}


def auth_url(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/auth/v1"


def make_token(user: dict[str, Any], base: str, lifetime: int = 3600) -> str:
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "aud": "authenticated",
        "role": "authenticated",
        "iss": f"{base}/auth/v1",
        "iat": int(time.time()),
        "exp": int(time.time()) + lifetime,
        "user_metadata": user.get("user_metadata") or {},
    }
    headers = {"kid": "mock-key-1"} if SIGNING_MODE == "rs256" else None
    return jwt.encode(payload, SECRET, algorithm="RS256" if SIGNING_MODE == "rs256" else "HS256", headers=headers)


def session_for(user: dict[str, Any], base: str) -> dict[str, Any]:
    refresh = secrets.token_urlsafe(24)
    refresh_tokens[refresh] = user["id"]
    return {
        "access_token": make_token(user, base),
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": 3600,
        "user": public_user(user),
    }


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "user_metadata": user.get("user_metadata") or {},
        "email_confirmed_at": "2026-01-01T00:00:00Z",
    }


def require_service(apikey: str | None, authorization: str | None) -> None:
    token = (authorization or "").replace("Bearer ", "")
    if apikey != SERVICE_KEY or token != SERVICE_KEY:
        raise HTTPException(401, "Invalid service key")


def require_anon(apikey: str | None) -> None:
    if apikey != ANON_KEY:
        raise HTTPException(401, "Invalid anon key")


def user_from_bearer(authorization: str | None) -> dict[str, Any]:
    token = (authorization or "").replace("Bearer ", "")
    if not token:
        raise HTTPException(401, "Missing token")
    try:
        claims = jwt.decode(token, SECRET, algorithms=["RS256" if SIGNING_MODE == "rs256" else "HS256"], audience="authenticated", options={"verify_aud": False})
    except jwt.PyJWTError as error:
        raise HTTPException(401, f"Bad token: {error}") from error
    user = users.get(claims["sub"])
    if not user:
        raise HTTPException(401, "Unknown user")
    return user


@app.get("/auth/v1/.well-known/jwks.json")
def jwks():
    return {"keys": [PUBLIC_JWK] if SIGNING_MODE == "rs256" else []}


@app.post("/auth/v1/admin/users")
def admin_create_user(
    request: Request,
    payload: dict = Body(...),
    apikey: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    require_service(apikey, authorization)
    email = (payload.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(422, "Email is required")
    if any(user["email"] == email for user in users.values()):
        raise HTTPException(422, "A user with this email address has already been registered")
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password": payload.get("password", ""),
        "user_metadata": payload.get("user_metadata") or {},
    }
    users[user["id"]] = user
    return public_user(user)


@app.delete("/auth/v1/admin/users/{user_id}")
def admin_delete_user(
    user_id: str, apikey: str | None = Header(default=None), authorization: str | None = Header(default=None)
):
    require_service(apikey, authorization)
    users.pop(user_id, None)
    return {}


@app.put("/auth/v1/admin/users/{user_id}")
def admin_update_user(
    user_id: str,
    payload: dict = Body(...),
    apikey: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    require_service(apikey, authorization)
    user = users.get(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if payload.get("password"):
        user["password"] = payload["password"]
    return public_user(user)


@app.post("/auth/v1/token")
def token(
    request: Request,
    grant_type: str,
    payload: dict = Body(...),
    apikey: str | None = Header(default=None),
):
    require_anon(apikey)
    base = str(request.base_url).rstrip("/")
    if grant_type == "password":
        email = (payload.get("email") or "").strip().lower()
        user = next((item for item in users.values() if item["email"] == email), None)
        if not user or user["password"] != payload.get("password"):
            return JSONResponse({"error": "invalid_grant", "error_description": "Invalid login credentials"}, status_code=400)
        return session_for(user, base)
    if grant_type == "refresh_token":
        user_id = refresh_tokens.get(payload.get("refresh_token", ""))
        user = users.get(user_id) if user_id else None
        if not user:
            return JSONResponse({"error": "invalid_grant", "error_description": "Invalid Refresh Token"}, status_code=400)
        return session_for(user, base)
    raise HTTPException(400, "Unsupported grant type")


@app.post("/auth/v1/logout")
def logout(apikey: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    require_anon(apikey)
    token = (authorization or "").replace("Bearer ", "")
    refresh_tokens.pop(token, None)
    return Response(status_code=204)


@app.get("/auth/v1/user")
def read_user(authorization: str | None = Header(default=None), apikey: str | None = Header(default=None)):
    require_anon(apikey)
    return public_user(user_from_bearer(authorization))


@app.put("/auth/v1/user")
def update_user(
    payload: dict = Body(...),
    authorization: str | None = Header(default=None),
    apikey: str | None = Header(default=None),
):
    require_anon(apikey)
    user = user_from_bearer(authorization)
    if payload.get("password"):
        user["password"] = payload["password"]
    return public_user(user)


@app.post("/auth/v1/recover")
def recover(
    request: Request,
    payload: dict = Body(...),
    apikey: str | None = Header(default=None),
):
    require_anon(apikey)
    email = (payload.get("email") or "").strip().lower()
    user = next((item for item in users.values() if item["email"] == email), None)
    return {
        "sent": True,
        "email": email,
        "redirect_to": payload.get("redirect_to", ""),
        "recovery_token": make_token(user, str(request.base_url).rstrip("/"), 900) if user else "",
    }


@app.post("/storage/v1/object/{bucket}/{path:path}")
async def storage_upload(
    bucket: str,
    path: str,
    request: Request,
    apikey: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    require_service(apikey, authorization)
    body = await request.body()
    objects[f"{bucket}/{path}"] = body
    return {"Key": f"{bucket}/{path}", "size": len(body)}


@app.get("/storage/v1/object/{bucket}/{path:path}")
def storage_download(
    bucket: str,
    path: str,
    apikey: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    require_service(apikey, authorization)
    data = objects.get(f"{bucket}/{path}")
    if data is None:
        raise HTTPException(404, "Object not found")
    return Response(content=data, media_type="application/octet-stream")


@app.delete("/storage/v1/object/{bucket}/{path:path}")
def storage_delete(
    bucket: str,
    path: str,
    apikey: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    require_service(apikey, authorization)
    objects.pop(f"{bucket}/{path}", None)
    return {}


@app.get("/__state")
def state():
    return {
        "users": [{"id": u["id"], "email": u["email"], "metadata": u.get("user_metadata")} for u in users.values()],
        "objects": sorted(objects),
        "signing": SIGNING_MODE,
    }
