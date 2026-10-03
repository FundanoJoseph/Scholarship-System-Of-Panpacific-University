import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..models import Application, Notification, User, utcnow


def push(
    db: Session,
    user_id: uuid.UUID,
    application_id: uuid.UUID | None,
    kind: str,
    message: str,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        application_id=application_id,
        type=kind,
        message=message,
        read=False,
    )
    db.add(notification)
    return notification


def notify_staff(db: Session, application: Application, message: str) -> None:
    staff = db.scalars(
        select(User).where(
            User.role.in_(("staff", "admin")),
            User.deleted_at.is_(None),
        )
    ).all()
    for member in staff:
        push(db, member.id, application.id, "admin", message)


def list_for_user(db: Session, user_id: uuid.UUID, limit: int = 100) -> list[Notification]:
    return list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user_id, Notification.deleted_at.is_(None))
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
    )


def unread_count(db: Session, user_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.deleted_at.is_(None),
                Notification.read.is_(False),
            )
        )
        or 0
    )


def mark_read(db: Session, user_id: uuid.UUID, notification_id: uuid.UUID) -> bool:
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
            Notification.deleted_at.is_(None),
        )
    )
    if not notification:
        return False
    notification.read = True
    db.commit()
    return True


def mark_all_read(db: Session, user_id: uuid.UUID) -> int:
    result = db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.deleted_at.is_(None),
            Notification.read.is_(False),
        )
        .values(read=True)
    )
    db.commit()
    return int(result.rowcount or 0)


def soft_delete_for_application(db: Session, application_id: uuid.UUID) -> None:
    db.execute(
        update(Notification)
        .where(Notification.application_id == application_id, Notification.deleted_at.is_(None))
        .values(deleted_at=utcnow())
    )
