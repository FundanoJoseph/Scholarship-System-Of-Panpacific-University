import hashlib
import secrets
import uuid
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models import PasswordResetToken, User, utcnow
from ..security import create_token_pair, decode_local_token, hash_password, password_problems, verify_password
from ..supabase_api import SupabaseAuth
from ..validation import (
    bad_request,
    check_email,
    check_letters_only,
    check_student_id,
    check_year_level,
    required,
)

RESET_TOKEN_MINUTES = 30


def find_by_email(db: Session, email: str) -> User | None:
    return db.scalar(
        select(User).where(
            func.lower(User.email) == (email or "").strip().lower(),
            User.deleted_at.is_(None),
        )
    )


def ensure_password_policy(password: str) -> str:
    problems = password_problems(password or "")
    if problems:
        raise bad_request(problems[0])
    return password


def _as_uuid(value) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _session_payload(session: dict) -> dict:
    return {
        "access_token": session.get("access_token", ""),
        "refresh_token": session.get("refresh_token", ""),
        "expires_in": int(session.get("expires_in", 3600) or 3600),
        "token_type": "bearer",
    }


def _supabase_sign_in(email: str, password: str) -> dict:
    return SupabaseAuth().sign_in(email, password)


def _link_supabase_user(db: Session, auth_user: dict, fallback_email: str) -> User:
    auth_user_id = _as_uuid(auth_user.get("id"))
    email = (auth_user.get("email") or fallback_email or "").strip().lower()

    user = None
    if auth_user_id is not None:
        user = db.scalar(select(User).where(User.auth_user_id == auth_user_id, User.deleted_at.is_(None)))
    if user is None and email:
        user = find_by_email(db, email)
        if user is not None and auth_user_id is not None and user.auth_user_id is None:
            user.auth_user_id = auth_user_id
            db.commit()

    if user is None:
        metadata = auth_user.get("user_metadata") or {}
        user = User(
            auth_user_id=auth_user_id,
            email=email,
            full_name=(metadata.get("full_name") or email.split("@")[0] or "Student").strip(),
            role="student",
            student_id="",
            program="",
            year_level="",
        )
        db.add(user)
        db.commit()
    return user


def _create_auth_account(email: str, password: str, full_name: str) -> uuid.UUID | None:
    try:
        created = SupabaseAuth().create_user(email, password, full_name)
    except HTTPException as error:
        detail = str(error.detail)
        if "already" in detail.lower() or error.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
            raise bad_request("An account with this email already exists.") from error
        raise
    return _as_uuid(created.get("id"))


def register_student(db: Session, payload: dict) -> tuple[User, dict]:
    full_name = check_letters_only(payload.get("fullName"), "Full name")
    student_id = check_student_id(payload.get("studentId"))
    email = check_email(payload.get("email"))
    program = check_letters_only(payload.get("program"), "Program/Course")
    year_level = check_year_level(payload.get("yearLevel"))
    password = ensure_password_policy(payload.get("password") or "")

    if find_by_email(db, email):
        raise bad_request("An account with this email already exists.")

    auth_user_id = None
    if settings.uses_supabase_auth:
        auth_user_id = _create_auth_account(email, password, full_name)

    user = User(
        auth_user_id=auth_user_id,
        email=email,
        full_name=full_name,
        role="student",
        student_id=student_id,
        program=program,
        year_level=year_level,
        password_hash=None if settings.uses_supabase_auth else hash_password(password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if auth_user_id is not None:
            SupabaseAuth().delete_user(str(auth_user_id))
        raise bad_request("An account with this email already exists.") from error

    session = _supabase_sign_in(email, password) if settings.uses_supabase_auth else create_token_pair(user)
    return user, _session_payload(session)


def authenticate(db: Session, email: str, password: str) -> tuple[User, dict]:
    email_value = (email or "").strip().lower()
    password_value = password or ""
    if not email_value or not password_value:
        raise bad_request("Please enter your email and password.")

    if settings.uses_supabase_auth:
        session = _supabase_sign_in(email_value, password_value)
        user = _link_supabase_user(db, session.get("user") or {}, email_value)
        return user, _session_payload(session)

    user = find_by_email(db, email_value)
    if not user or not verify_password(password_value, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    return user, create_token_pair(user)


def refresh_session(db: Session, refresh_token: str) -> tuple[User, dict]:
    token = (refresh_token or "").strip()
    if not token:
        raise bad_request("Please log in again.")

    if settings.uses_supabase_auth:
        auth = SupabaseAuth()
        session = auth.refresh(token)
        claims = auth.verify_access_token(session.get("access_token", "")) or {}
        user = db.scalar(
            select(User).where(User.auth_user_id == _as_uuid(claims.get("sub")), User.deleted_at.is_(None))
        )
        if user is None:
            user = _link_supabase_user(db, session.get("user") or claims, claims.get("email", ""))
        return user, _session_payload(session)

    payload = decode_local_token(token, "refresh")
    user = db.scalar(select(User).where(User.id == _as_uuid(payload.get("sub")), User.deleted_at.is_(None)))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Please log in again.")
    return user, create_token_pair(user)


def sign_out(access_token: str) -> None:
    if settings.uses_supabase_auth and access_token:
        try:
            SupabaseAuth().sign_out(access_token)
        except HTTPException:
            pass


def request_password_reset(db: Session, email: str) -> dict:
    email_value = check_email(email)
    user = find_by_email(db, email_value)
    if not user:
        raise bad_request("No account was found with that email.")

    if settings.uses_supabase_auth:
        redirect = settings.password_reset_redirect or f"{settings.site_url}/template/reset-password.html"
        SupabaseAuth().send_recovery_email(user.email, redirect)
        return {"emailed": True}

    if not settings.is_development:
        raise bad_request(
            "Password reset by e-mail is not switched on for this deployment yet. "
            "Please ask the CSS Office to reset your password."
        )

    raw_token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            expires_at=utcnow() + timedelta(minutes=RESET_TOKEN_MINUTES),
        )
    )
    db.commit()

    return {"emailed": False, "resetToken": raw_token}


def confirm_password_reset(db: Session, token: str, new_password: str) -> None:
    password = ensure_password_policy(new_password)

    if settings.uses_supabase_auth:
        SupabaseAuth().update_own_password((token or "").strip(), password)
        return

    token_hash = hashlib.sha256((token or "").strip().encode("utf-8")).hexdigest()
    record = db.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > utcnow(),
        )
        .order_by(PasswordResetToken.created_at.desc())
    )
    if not record:
        raise bad_request('This reset link is no longer valid. Please start again from "Forgot password?".')

    user = db.get(User, record.user_id)
    if not user or user.deleted_at is not None:
        raise bad_request("Account not found.")

    user.password_hash = hash_password(password)
    record.used_at = utcnow()
    db.commit()


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    current = current_password or ""
    if not current:
        raise bad_request("Current password is required.")
    password = ensure_password_policy(new_password)

    if settings.uses_supabase_auth:
        try:
            _supabase_sign_in(user.email, current)
        except HTTPException as error:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.") from error
        if user.auth_user_id is None:
            raise bad_request("This account is not linked to the sign-in service.")
        SupabaseAuth().update_password(str(user.auth_user_id), password)
        return

    if not verify_password(current, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
    user.password_hash = hash_password(password)
    db.commit()


def list_staff_accounts(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.role.in_(("staff", "admin")), User.deleted_at.is_(None))
            .order_by(User.created_at.asc())
        )
    )


def create_staff_account(db: Session, actor: User, payload: dict) -> User:
    if actor.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an Admin can create Staff or Admin accounts.")

    role = required(payload.get("role"), "Role").lower()
    if role not in ("staff", "admin"):
        raise bad_request("Please choose Authorized Staff or Admin.")
    full_name = check_letters_only(payload.get("fullName"), "Full name")
    email = check_email(payload.get("email"))
    password = ensure_password_policy(payload.get("password") or "")

    if find_by_email(db, email):
        raise bad_request("An account with this email already exists.")

    auth_user_id = None
    if settings.uses_supabase_auth:
        auth_user_id = _create_auth_account(email, password, full_name)

    user = User(
        auth_user_id=auth_user_id,
        email=email,
        full_name=full_name,
        role=role,
        student_id="",
        program="",
        year_level="",
        password_hash=None if settings.uses_supabase_auth else hash_password(password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if auth_user_id is not None:
            SupabaseAuth().delete_user(str(auth_user_id))
        raise bad_request("An account with this email already exists.") from error
    return user


def update_own_profile(db: Session, user: User, payload: dict) -> User:
    if user.role != "student":
        return user
    program = payload.get("program")
    year_level = payload.get("yearLevel")
    if program is not None and str(program).strip():
        user.program = check_letters_only(program, "Program/Course")
    if year_level is not None and str(year_level).strip():
        user.year_level = check_year_level(year_level)
    db.commit()
    return user
