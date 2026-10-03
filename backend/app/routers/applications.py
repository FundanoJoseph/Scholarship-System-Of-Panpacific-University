import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ApplicationDocument, User, utcnow
from ..schemas import ApplicationIn, DiscountIn, StatusIn
from ..security import get_current_user, require_roles
from ..serializers import application_public, document_public
from ..services import applications as service
from ..storage import check_upload, get_storage, storage_path_for
from ..validation import REQUIREMENT_KEYS, bad_request

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("")
def list_applications(
    scope: str = "active",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope = (scope or "active").lower()
    if user.role == "student":
        items = (
            service.list_for_student(db, user.id)
            if scope in ("all", "mine")
            else service.list_active_for_student(db, user.id)
        )
    else:
        items = service.list_all(db) if scope in ("all",) else service.list_active(db)
    return {"applications": [application_public(item) for item in items]}


@router.get("/history")
def application_history(
    actor: User = Depends(require_roles("staff", "admin")),
    db: Session = Depends(get_db),
):
    return {"rows": service.audit_rows(db)}


@router.get("/{application_id}")
def read_application(
    application_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = service.get_visible(db, application_id, user)
    return {"application": application_public(application)}


@router.post("")
def create_application(
    payload: str = Form(...),
    copyOfGrades: UploadFile | None = File(default=None),
    letterOfIntent: UploadFile | None = File(default=None),
    notarizedAgreement: UploadFile | None = File(default=None),
    student: User = Depends(require_roles("student")),
    db: Session = Depends(get_db),
):
    try:
        parsed = ApplicationIn.model_validate_json(payload)
    except ValueError as error:
        raise bad_request("The application details could not be read.") from error

    uploads = {
        "copyOfGrades": copyOfGrades,
        "letterOfIntent": letterOfIntent,
        "notarizedAgreement": notarizedAgreement,
    }
    files: dict[str, tuple[str, bytes, str | None]] = {}
    for key, upload in uploads.items():
        if upload is None:
            continue
        data = upload.file.read()
        files[key] = (upload.filename or f"{key}", data, upload.content_type)

    application = service.create(db, student, parsed.model_dump(), files)
    return {"application": application_public(application)}


@router.post("/{application_id}/status")
def set_status(
    application_id: uuid.UUID,
    payload: StatusIn,
    actor: User = Depends(require_roles("staff", "admin")),
    db: Session = Depends(get_db),
):
    application = service.update_status(
        db, actor, application_id, payload.status, payload.remarks, payload.discountPercent
    )
    return {"application": application_public(application)}


@router.patch("/{application_id}/discount")
def set_discount(
    application_id: uuid.UUID,
    payload: DiscountIn,
    actor: User = Depends(require_roles("staff", "admin")),
    db: Session = Depends(get_db),
):
    application = service.update_discount(db, actor, application_id, payload.discountPercent)
    return {"application": application_public(application)}


@router.delete("/{application_id}")
def delete_application(
    application_id: uuid.UUID,
    actor: User = Depends(require_roles("staff", "admin")),
    db: Session = Depends(get_db),
):
    return {"application": service.soft_delete(db, actor, application_id)}


@router.get("/{application_id}/documents/{requirement_key}")
def download_document(
    application_id: uuid.UUID,
    requirement_key: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = service.accessible_document(db, application_id, user, requirement_key)
    data = get_storage().get(document.storage_path)
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The document file is no longer available.")
    filename = quote(document.file_name)
    return Response(
        content=data,
        media_type=document.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{filename}",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/{application_id}/documents/{requirement_key}")
def upload_document(
    application_id: uuid.UUID,
    requirement_key: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if requirement_key not in REQUIREMENT_KEYS:
        raise bad_request("Unknown document requirement.")
    application = service.get_visible(db, application_id, user)
    if user.role == "student" and application.student_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only change documents on your own application.")
    if application.archived:
        raise bad_request(
            f"This application belongs to {application.term_label} and can no longer be changed."
        )

    data = file.file.read()
    file_name = file.filename or requirement_key
    check_upload(file_name, len(data), file.content_type)

    storage = get_storage()
    path = storage_path_for(application.student_user_id, application.id, requirement_key, file_name)
    storage.put(path, data, file.content_type)

    for document in application.documents:
        if document.requirement_key == requirement_key and document.deleted_at is None:
            document.deleted_at = utcnow()

    record = ApplicationDocument(
        application_id=application.id,
        requirement_key=requirement_key,
        file_name=file_name,
        storage_path=path,
        content_type=file.content_type,
        size_bytes=len(data),
    )
    application.documents.append(record)
    application.updated_at = utcnow()
    db.commit()
    db.refresh(record)
    return {"document": document_public(record)}
