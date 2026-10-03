from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    ChangePasswordIn,
    LoginIn,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    RefreshIn,
    RegisterIn,
)
from ..security import get_current_user, get_optional_user
from ..serializers import user_public
from ..services import accounts

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    user, session = accounts.register_student(db, payload.model_dump())
    return {"user": user_public(user), **session}


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user, session = accounts.authenticate(db, payload.email, payload.password)
    return {"user": user_public(user), **session}


@router.post("/refresh")
def refresh(payload: RefreshIn, db: Session = Depends(get_db)):
    user, session = accounts.refresh_session(db, payload.refreshToken)
    return {"user": user_public(user), **session}


@router.post("/logout")
def logout(request: Request, user: User | None = Depends(get_optional_user)):
    header = request.headers.get("authorization") or ""
    accounts.sign_out(header.partition(" ")[2].strip())
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user": user_public(user)}


@router.post("/password-reset/request")
def password_reset_request(payload: PasswordResetRequestIn, db: Session = Depends(get_db)):
    return accounts.request_password_reset(db, payload.email)


@router.post("/password-reset/confirm")
def password_reset_confirm(payload: PasswordResetConfirmIn, db: Session = Depends(get_db)):
    accounts.confirm_password_reset(db, payload.token, payload.newPassword)
    return {"ok": True}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    accounts.change_password(db, user, payload.currentPassword, payload.newPassword)
    return {"ok": True}
