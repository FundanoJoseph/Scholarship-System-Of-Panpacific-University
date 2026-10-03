import base64
import hashlib
import re
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User, utcnow
from .supabase_api import SupabaseAuth

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PASSWORD_SPECIAL_CHARS = r"!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`"
PASSWORD_SPECIAL_RE = re.compile(f"[{PASSWORD_SPECIAL_CHARS}]")
TOKEN_ISSUER = "sams-api"


def password_problems(password: str) -> list[str]:
    problems: list[str] = []
    text = password or ""
    if len(text) < PASSWORD_MIN_LENGTH:
        problems.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if len(text) > PASSWORD_MAX_LENGTH:
        problems.append(f"Password must be at most {PASSWORD_MAX_LENGTH} characters long.")
    if not re.search(r"[A-Z]", text):
        problems.append("Password must include at least 1 uppercase letter.")
    if not re.search(r"[0-9]", text):
        problems.append("Password must include at least 1 number.")
    if not PASSWORD_SPECIAL_RE.search(text):
        problems.append("Password must include at least 1 special character.")
    return problems


def _prefold(password: str) -> bytes:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prefold(password), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_prefold(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_token(subject: uuid.UUID | str, kind: str, lifetime: timedelta, role: str = "") -> str:
    issued = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "typ": kind,
        "iss": TOKEN_ISSUER,
        "iat": int(issued.timestamp()),
        "exp": int((issued + lifetime).timestamp()),
    }
    if role:
        payload["role"] = role
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_token_pair(user: User) -> dict[str, Any]:
    access = create_token(user.id, "access", timedelta(minutes=settings.access_token_minutes), user.role)
    refresh = create_token(user.id, "refresh", timedelta(days=settings.refresh_token_days))
    return {
        "access_token": access,
        "refresh_token": refresh,
        "expires_in": settings.access_token_minutes * 60,
        "token_type": "bearer",
    }


def decode_local_token(token: str, expected_kind: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=TOKEN_ISSUER,
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Please log in again.") from error
    if payload.get("typ") != expected_kind:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This token cannot be used here.")
    return payload


def bearer_token(request: Request) -> str:
    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please log in to continue.")
    return token.strip()


def user_from_local_token(db: Session, token: str) -> User | None:
    payload = decode_local_token(token, "access")
    try:
        user_id = uuid.UUID(payload.get("sub", ""))
    except (ValueError, TypeError):
        return None
    return db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))


def user_from_supabase_token(db: Session, token: str) -> User | None:
    auth = SupabaseAuth()
    claims = auth.verify_access_token(token)
    if not claims:
        return None

    subject = claims.get("sub")
    auth_user_id: uuid.UUID | None = None
    if subject:
        try:
            auth_user_id = uuid.UUID(str(subject))
        except (ValueError, TypeError):
            auth_user_id = None

    if auth_user_id is not None:
        user = db.scalar(select(User).where(User.auth_user_id == auth_user_id, User.deleted_at.is_(None)))
        if user:
            return user

    email = (claims.get("email") or "").strip().lower()
    if not email:
        return None
    user = db.scalar(
        select(User).where(func.lower(User.email) == email, User.deleted_at.is_(None))
    )
    if user and auth_user_id is not None and user.auth_user_id is None:
        user.auth_user_id = auth_user_id
        db.commit()
    return user


def resolve_user(db: Session, token: str) -> User | None:
    if settings.uses_supabase_auth:
        return user_from_supabase_token(db, token)
    return user_from_local_token(db, token)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = resolve_user(db, bearer_token(request))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please log in to continue.")
    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return resolve_user(db, token.strip())


def require_roles(*roles: str) -> Callable[[User], User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your account is not allowed to do this.")
        return user

    return dependency


def now() -> datetime:
    return utcnow()
