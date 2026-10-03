import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..serializers import notification_public
from ..services import notifications

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = notifications.list_for_user(db, user.id)
    return {"notifications": [notification_public(item) for item in items]}


@router.get("/unread-count")
def read_unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"count": notifications.unread_count(db, user.id)}


@router.post("/read-all")
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"updated": notifications.mark_all_read(db, user.id)}


@router.post("/{notification_id}/read")
def read_one(notification_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        parsed = uuid.UUID(notification_id)
    except ValueError:
        return {"ok": False}
    return {"ok": notifications.mark_read(db, user.id, parsed)}
