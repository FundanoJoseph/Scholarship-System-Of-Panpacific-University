import re
import uuid
from pathlib import Path

import httpx
from fastapi import HTTPException, status

from .config import settings

SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]")
ALLOWED_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png")


def safe_file_name(name: str) -> str:
    cleaned = SAFE_NAME_RE.sub("_", name or "file")
    return cleaned[-120:] or "file"


def storage_path_for(user_id: uuid.UUID | str, application_id: uuid.UUID | str, requirement_key: str, file_name: str) -> str:
    return f"{user_id}/{application_id}/{requirement_key}-{safe_file_name(file_name)}"


def check_upload(file_name: str, size_bytes: int, content_type: str | None) -> None:
    lower = (file_name or "").lower()
    if not lower.endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported file type for {file_name}. Accepted: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    limit = settings.max_upload_mb * 1024 * 1024
    if size_bytes > limit:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"{file_name} is too large. Maximum size is {settings.max_upload_mb}MB.",
        )
    if content_type and content_type not in {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "application/octet-stream",
    }:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported content type for {file_name}.")


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        target = (self.root / path).resolve()
        if not str(target).startswith(str(self.root)):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid document path.")
        return target

    def put(self, path: str, data: bytes, content_type: str | None = None) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def get(self, path: str) -> bytes | None:
        target = self._resolve(path)
        if not target.is_file():
            return None
        return target.read_bytes()

    def delete(self, path: str) -> None:
        target = self._resolve(path)
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass


class SupabaseStorage:
    def __init__(self, bucket: str) -> None:
        self.bucket = bucket
        self.base_url = f"{settings.supabase_root}/storage/v1/object"

    def _headers(self, content_type: str | None = None) -> dict[str, str]:
        key = settings.supabase_service_key
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def put(self, path: str, data: bytes, content_type: str | None = None) -> None:
        try:
            response = httpx.post(
                f"{self.base_url}/{self.bucket}/{path}",
                content=data,
                headers={**self._headers(content_type or "application/octet-stream"), "x-upsert": "true"},
                timeout=settings.supabase_timeout,
            )
        except httpx.HTTPError as error:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not reach document storage.") from error
        if response.status_code >= 400:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not save the uploaded document.")

    def get(self, path: str) -> bytes | None:
        try:
            response = httpx.get(
                f"{self.base_url}/{self.bucket}/{path}",
                headers=self._headers(),
                timeout=settings.supabase_timeout,
            )
        except httpx.HTTPError as error:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not reach document storage.") from error
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not open the document.")
        return response.content

    def delete(self, path: str) -> None:
        try:
            httpx.request(
                "DELETE",
                f"{self.base_url}/{self.bucket}/{path}",
                headers=self._headers(),
                timeout=settings.supabase_timeout,
            )
        except httpx.HTTPError:
            pass


def get_storage() -> LocalStorage | SupabaseStorage:
    if settings.uses_supabase_storage:
        return SupabaseStorage(settings.storage_bucket)
    return LocalStorage(settings.resolved_upload_dir)
