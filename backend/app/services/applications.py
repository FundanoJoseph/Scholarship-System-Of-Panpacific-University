import uuid
from collections import defaultdict
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Application, ApplicationCounter, ApplicationDocument, ApplicationHistory, User, utcnow
from ..serializers import audit_row, application_public
from ..storage import check_upload, get_storage, storage_path_for
from ..validation import (
    REQUIREMENT_KEYS,
    REQUIREMENT_LABELS,
    bad_request,
    check_discount,
    check_letters_only,
    check_scholarship_type,
    check_year_level,
    required,
)
from . import notifications, terms

ALLOWED_TRANSITIONS = {
    "Submitted": ("Under Evaluation",),
    "Under Evaluation": ("Approved", "Rejected"),
    "Approved": (),
    "Rejected": (),
}

STATUS_FILTERS = ("Submitted", "Under Evaluation", "Approved", "Rejected")


def not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Application not found.")


def next_code(db: Session) -> str:
    year = datetime.now().year
    counter = db.scalar(
        select(ApplicationCounter).where(ApplicationCounter.year == year).with_for_update()
    )
    if counter is None:
        counter = ApplicationCounter(year=year, last_value=0)
        db.add(counter)
        db.flush()
    counter.last_value += 1
    return f"APP-{year}-{counter.last_value:04d}"


def get_or_404(db: Session, application_id: uuid.UUID, include_deleted: bool = False) -> Application:
    query = select(Application).where(Application.id == application_id)
    if not include_deleted:
        query = query.where(Application.deleted_at.is_(None))
    application = db.scalar(query)
    if not application:
        raise not_found()
    return application


def get_visible(db: Session, application_id: uuid.UUID, user: User) -> Application:
    application = get_or_404(db, application_id)
    if user.role == "student" and application.student_user_id != user.id:
        raise not_found()
    return application


def accessible_document(db: Session, application_id: uuid.UUID, user: User, requirement_key: str) -> ApplicationDocument:
    if requirement_key not in REQUIREMENT_KEYS:
        raise not_found()
    application = get_visible(db, application_id, user)
    document = db.scalar(
        select(ApplicationDocument).where(
            ApplicationDocument.application_id == application.id,
            ApplicationDocument.requirement_key == requirement_key,
            ApplicationDocument.deleted_at.is_(None),
        )
    )
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That document was not found.")
    return document


def list_active(db: Session) -> list[Application]:
    return list(
        db.scalars(
            select(Application)
            .where(Application.deleted_at.is_(None), Application.archived.is_(False))
            .order_by(Application.date_submitted.desc())
        )
    )


def list_all(db: Session) -> list[Application]:
    return list(
        db.scalars(
            select(Application)
            .where(Application.deleted_at.is_(None))
            .order_by(Application.date_submitted.desc())
        )
    )


def list_for_student(db: Session, student_id: uuid.UUID) -> list[Application]:
    return list(
        db.scalars(
            select(Application)
            .where(Application.student_user_id == student_id, Application.deleted_at.is_(None))
            .order_by(Application.date_submitted.desc())
        )
    )


def list_active_for_student(db: Session, student_id: uuid.UUID) -> list[Application]:
    return list(
        db.scalars(
            select(Application)
            .where(
                Application.student_user_id == student_id,
                Application.deleted_at.is_(None),
                Application.archived.is_(False),
            )
            .order_by(Application.date_submitted.desc())
        )
    )


def audit_rows(db: Session) -> list[dict]:
    entries = db.execute(
        select(ApplicationHistory, Application)
        .join(Application, ApplicationHistory.application_id == Application.id)
        .order_by(ApplicationHistory.application_id, ApplicationHistory.created_at)
    ).all()

    grouped: dict[uuid.UUID, list[tuple[ApplicationHistory, Application]]] = defaultdict(list)
    for entry, application in entries:
        grouped[application.id].append((entry, application))

    rows: list[dict] = []
    for group in grouped.values():
        for index in range(1, len(group)):
            entry, application = group[index]
            previous_status = group[index - 1][0].status
            rows.append(audit_row(application, entry, previous_status))

    rows.sort(key=lambda row: row["date"] or "", reverse=True)
    return rows


def create(
    db: Session,
    student: User,
    payload: dict,
    files: dict[str, tuple[str, bytes, str | None]],
) -> Application:
    if student.role != "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only student accounts can submit applications.")

    program = check_letters_only(payload.get("program"), "Degree program")
    year_level = check_year_level(payload.get("yearLevel"))
    scholarship_type = check_scholarship_type(payload.get("scholarshipType"))

    missing = [REQUIREMENT_LABELS[key] for key in REQUIREMENT_KEYS if key not in files]
    if missing:
        raise bad_request(f"Missing required document(s): {', '.join(missing)}.")

    for key in REQUIREMENT_KEYS:
        file_name, data, content_type = files[key]
        check_upload(file_name or "", len(data), content_type)

    term = terms.current_term(db)
    storage = get_storage()

    last_error: IntegrityError | None = None
    for _ in range(3):
        try:
            application = Application(
                code=next_code(db),
                student_user_id=student.id,
                term_id=term.id,
                term_label=term.label,
                student_name=student.full_name,
                student_id=student.student_id,
                university_email=student.email,
                program=program,
                year_level=year_level,
                gwa=required(payload.get("gwa"), "GWA") if payload.get("gwa") else "",
                scholarship_type=scholarship_type,
                status="Submitted",
                remarks="",
                evaluated_by="",
                discount_percent="",
                date_submitted=utcnow(),
                archived=False,
            )
            db.add(application)
            db.flush()

            application.history.append(
                ApplicationHistory(
                    application_id=application.id,
                    status="Submitted",
                    remarks="Application submitted.",
                    actor_user_id=student.id,
                    actor_name=student.full_name,
                )
            )

            for key in REQUIREMENT_KEYS:
                file_name, data, content_type = files[key]
                storage.put(
                    storage_path_for(student.id, application.id, key, file_name),
                    data,
                    content_type,
                )
                application.documents.append(
                    ApplicationDocument(
                        application_id=application.id,
                        requirement_key=key,
                        file_name=file_name,
                        storage_path=storage_path_for(student.id, application.id, key, file_name),
                        content_type=content_type,
                        size_bytes=len(data),
                    )
                )

            application.updated_at = utcnow()
            notifications.push(
                db,
                student.id,
                application.id,
                "status",
                f"Your {application.scholarship_type} application ({application.code}) was submitted successfully.",
            )
            notifications.notify_staff(
                db,
                application,
                f"New application {application.code} was submitted by {application.student_name}.",
            )
            db.commit()
            return application
        except IntegrityError as error:
            db.rollback()
            last_error = error

    raise HTTPException(
        status.HTTP_409_CONFLICT,
        "The application could not be saved. Please try submitting again.",
    ) from last_error


def update_status(
    db: Session,
    actor: User,
    application_id: uuid.UUID,
    new_status: str,
    remarks: str | None,
    discount_percent: str | None,
) -> Application:
    if actor.role not in ("staff", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only Authorized Staff or Admin can evaluate applications.")

    new_status = required(new_status, "Status")
    if new_status not in STATUS_FILTERS:
        raise bad_request("Please choose a valid status.")

    application = get_or_404(db, application_id)
    if application.archived:
        raise bad_request(
            f"This application belongs to {application.term_label} and can no longer be evaluated. "
            "It is kept for records only."
        )
    if new_status not in ALLOWED_TRANSITIONS.get(application.status, ()):
        raise bad_request(f"An application cannot move from {application.status} to {new_status}.")

    note = (remarks or "").strip()
    if new_status == "Rejected" and not note:
        raise bad_request("Remarks are required to reject an application.")

    if new_status == "Approved":
        discount = check_discount(discount_percent)
        if discount:
            application.discount_percent = discount

    application.status = new_status
    application.remarks = note
    application.evaluated_by = actor.full_name
    application.updated_at = utcnow()
    application.history.append(
        ApplicationHistory(
            application_id=application.id,
            status=new_status,
            remarks=note,
            actor_user_id=actor.id,
            actor_name=actor.full_name,
        )
    )

    message = f"Your {application.scholarship_type} application ({application.code})"
    if new_status == "Under Evaluation":
        message += " moved to Under Evaluation."
    elif new_status == "Approved":
        message += " was Approved." + (f" Remarks: {note}" if note else "")
        message += " Please proceed to the CSS Office for the next steps."
    else:
        message += (
            f" was Rejected. Reason: {note} You may visit the CSS Office if you need clarification."
        )
    notifications.push(db, application.student_user_id, application.id, "status", message)

    db.commit()
    return application


def update_discount(db: Session, actor: User, application_id: uuid.UUID, discount_percent: str | None) -> Application:
    if actor.role not in ("staff", "admin"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only Authorized Staff or Admin can edit the tuition fee discount."
        )

    application = get_or_404(db, application_id)
    if application.status != "Approved":
        raise bad_request("Only approved applications have a tuition fee discount to edit.")

    application.discount_percent = check_discount(discount_percent)
    application.updated_at = utcnow()
    db.commit()
    return application


def soft_delete(db: Session, actor: User, application_id: uuid.UUID) -> dict:
    if actor.role not in ("staff", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only Authorized Staff or Admin can delete applications.")

    application = get_or_404(db, application_id)
    storage = get_storage()
    for document in application.documents:
        if document.deleted_at is None:
            storage.delete(document.storage_path)
            document.deleted_at = utcnow()

    notifications.soft_delete_for_application(db, application.id)
    application.deleted_at = utcnow()
    application.updated_at = utcnow()
    db.commit()

    payload = application_public(application)
    payload["documents"] = {}
    return payload
