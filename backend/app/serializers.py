from typing import Any

from .models import Application, ApplicationDocument, ApplicationHistory, Notification, Term, User


def iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def user_public(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "role": user.role,
        "fullName": user.full_name,
        "email": user.email,
        "studentId": user.student_id,
        "program": user.program,
        "yearLevel": user.year_level,
        "createdAt": iso(user.created_at),
    }


def term_public(term: Term) -> dict[str, Any]:
    return {
        "trimester": term.trimester,
        "academicYear": term.academic_year,
        "label": term.label,
    }


def document_public(document: ApplicationDocument) -> dict[str, Any]:
    return {
        "name": document.file_name,
        "path": document.storage_path,
        "uploadedAt": iso(document.uploaded_at),
    }


def documents_map(application: Application) -> dict[str, Any]:
    return {
        document.requirement_key: document_public(document)
        for document in application.documents
        if document.deleted_at is None
    }


def history_public(entry: ApplicationHistory) -> dict[str, Any]:
    return {
        "status": entry.status,
        "date": iso(entry.created_at),
        "by": entry.actor_name,
        "remarks": entry.remarks,
    }


def application_public(application: Application, include_history: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(application.id),
        "code": application.code,
        "studentUserId": str(application.student_user_id),
        "studentName": application.student_name,
        "studentId": application.student_id,
        "universityEmail": application.university_email,
        "program": application.program,
        "yearLevel": application.year_level,
        "gwa": application.gwa,
        "scholarshipType": application.scholarship_type,
        "status": application.status,
        "remarks": application.remarks,
        "evaluatedBy": application.evaluated_by,
        "discountPercent": application.discount_percent,
        "dateSubmitted": iso(application.date_submitted),
        "term": application.term_label,
        "archived": application.archived,
        "deleted": application.deleted_at is not None,
        "deletedAt": iso(application.deleted_at),
        "documents": documents_map(application),
    }
    if include_history:
        payload["history"] = [history_public(entry) for entry in application.history]
    return payload


def audit_row(application: Application, entry: ApplicationHistory, previous_status: str) -> dict[str, Any]:
    return {
        "code": application.code,
        "term": application.term_label,
        "archived": application.archived,
        "deleted": application.deleted_at is not None,
        "studentName": application.student_name,
        "studentId": application.student_id,
        "scholarshipType": application.scholarship_type,
        "previousStatus": previous_status,
        "newStatus": entry.status,
        "date": iso(entry.created_at),
        "remarks": entry.remarks,
    }


def notification_public(notification: Notification) -> dict[str, Any]:
    return {
        "id": str(notification.id),
        "userId": str(notification.user_id),
        "appId": str(notification.application_id) if notification.application_id else "",
        "type": notification.type,
        "message": notification.message,
        "date": iso(notification.created_at),
        "read": notification.read,
    }
