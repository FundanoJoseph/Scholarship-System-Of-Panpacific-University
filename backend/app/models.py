import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base, TZDateTime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


SOFT_DELETE_ACTIVE = "deleted_at is null"

STATUSES = ("Submitted", "Under Evaluation", "Approved", "Rejected")
TRIMESTERS = ("1st Trimester", "2nd Trimester", "3rd Trimester")
ROLES = ("student", "staff", "admin")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    auth_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="student", server_default="student")
    password_hash: Mapped[str | None] = mapped_column(Text)
    student_id: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    program: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    year_level: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    __table_args__ = (
        CheckConstraint("role in ('student', 'staff', 'admin')", name="users_role_check"),
        Index(
            "users_email_unique",
            func.lower(email),
            unique=True,
            postgresql_where=text(SOFT_DELETE_ACTIVE),
            sqlite_where=text(SOFT_DELETE_ACTIVE),
        ),
        Index(
            "users_role_idx",
            "role",
            postgresql_where=text(SOFT_DELETE_ACTIVE),
            sqlite_where=text(SOFT_DELETE_ACTIVE),
        ),
    )


class Term(Base):
    __tablename__ = "terms"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    trimester: Mapped[str] = mapped_column(Text, nullable=False)
    academic_year: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=utcnow, server_default=func.now()
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    __table_args__ = (
        CheckConstraint(
            "trimester in ('1st Trimester', '2nd Trimester', '3rd Trimester')",
            name="terms_trimester_check",
        ),
        Index(
            "terms_single_current",
            "is_current",
            unique=True,
            postgresql_where=text("is_current and deleted_at is null"),
            sqlite_where=text("is_current and deleted_at is null"),
        ),
    )


class ApplicationCounter(Base):
    __tablename__ = "application_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    student_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    term_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("terms.id"))
    term_label: Mapped[str] = mapped_column(Text, nullable=False)
    student_name: Mapped[str] = mapped_column(Text, nullable=False)
    student_id: Mapped[str] = mapped_column(Text, nullable=False)
    university_email: Mapped[str] = mapped_column(Text, nullable=False)
    program: Mapped[str] = mapped_column(Text, nullable=False)
    year_level: Mapped[str] = mapped_column(Text, nullable=False)
    gwa: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    scholarship_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="Submitted", server_default="Submitted")
    remarks: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    evaluated_by: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    discount_percent: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    date_submitted: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=utcnow, server_default=func.now()
    )
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    documents: Mapped[list["ApplicationDocument"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", lazy="selectin"
    )
    history: Mapped[list["ApplicationHistory"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ApplicationHistory.created_at",
    )

    __table_args__ = (
        CheckConstraint(
            "status in ('Submitted', 'Under Evaluation', 'Approved', 'Rejected')",
            name="applications_status_check",
        ),
        Index(
            "applications_active_idx",
            "date_submitted",
            postgresql_where=text("deleted_at is null and archived = false"),
            sqlite_where=text("deleted_at is null and archived = 0"),
        ),
        Index(
            "applications_student_idx",
            "student_user_id",
            "date_submitted",
            postgresql_where=text(SOFT_DELETE_ACTIVE),
            sqlite_where=text(SOFT_DELETE_ACTIVE),
        ),
        Index("applications_audit_idx", "deleted_at", "archived"),
    )


class ApplicationDocument(Base):
    __tablename__ = "application_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    requirement_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    uploaded_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=utcnow, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    application: Mapped[Application] = relationship(back_populates="documents")

    __table_args__ = (
        Index(
            "application_documents_unique",
            "application_id",
            "requirement_key",
            unique=True,
            postgresql_where=text(SOFT_DELETE_ACTIVE),
            sqlite_where=text(SOFT_DELETE_ACTIVE),
        ),
    )


class ApplicationHistory(Base):
    __tablename__ = "application_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    remarks: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    actor_name: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=utcnow, server_default=func.now()
    )

    application: Mapped[Application] = relationship(back_populates="history")

    __table_args__ = (
        Index("application_history_app_idx", "application_id", "created_at"),
        Index("application_history_created_idx", "created_at"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("applications.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(Text, nullable=False, default="status", server_default="status")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=utcnow, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    __table_args__ = (
        CheckConstraint("type in ('status', 'admin')", name="notifications_type_check"),
        Index(
            "notifications_user_idx",
            "user_id",
            "created_at",
            postgresql_where=text(SOFT_DELETE_ACTIVE),
            sqlite_where=text(SOFT_DELETE_ACTIVE),
        ),
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=utcnow, server_default=func.now()
    )

    __table_args__ = (Index("password_reset_tokens_user_idx", "user_id", "created_at"),)
