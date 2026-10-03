from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import ProfileIn, StaffAccountIn
from ..security import get_current_user, require_roles
from ..serializers import user_public
from ..services import accounts

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def list_users(admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    accounts_list = accounts.list_staff_accounts(db)
    return {"users": [user_public(item) for item in accounts_list]}


@router.post("")
def create_user(payload: StaffAccountIn, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    user = accounts.create_staff_account(db, admin, payload.model_dump())
    return {"user": user_public(user)}


@router.patch("/me")
def update_me(payload: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    updated = accounts.update_own_profile(db, user, payload.model_dump())
    return {"user": user_public(updated)}
