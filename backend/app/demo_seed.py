"""Create the sample accounts and applications directly in the database.

`seed_dev.py` drives the running API and is best for local development.
This module does the same work straight through the database layer, so it can
run during startup (SEED_DEMO_ACCOUNTS=true) or on a Render Shell:

    python -m app.demo_seed
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .models import Application, User
from .security import hash_password
from .services import applications as applications_service
from .services import terms as terms_service
from .validation import REQUIREMENT_KEYS

logger = logging.getLogger("sams")

DEMO_PASSWORD = "Panpacific#2026"

DEMO_USERS = [
    {"email": "admin@panpacificu.edu.ph", "full_name": "CSS Administrator", "role": "admin", "student_id": "0000001", "program": "CSS Office", "year_level": "1st Year"},
    {"email": "staff@panpacificu.edu.ph", "full_name": "Reyna Cruz", "role": "staff", "student_id": "", "program": "", "year_level": ""},
    {"email": "juan.delacruz@panpacificu.edu.ph", "full_name": "Juan Dela Cruz", "role": "student", "student_id": "1234567", "program": "BS Computer Science", "year_level": "3rd Year"},
    {"email": "ana.reyes@panpacificu.edu.ph", "full_name": "Ana Reyes", "role": "student", "student_id": "7654321", "program": "BS Accountancy", "year_level": "2nd Year"},
]

DEMO_APPLICATIONS = [
    {"email": "juan.delacruz@panpacificu.edu.ph", "scholarship": "Academic Scholarship", "decisions": []},
    {
        "email": "ana.reyes@panpacificu.edu.ph",
        "scholarship": "Entrance Exam Scholarship",
        "decisions": [
            ("Under Evaluation", "", ""),
            ("Rejected", "Entrance examination score is below the qualifying cut-off.", ""),
        ],
    },
    {
        "email": "ana.reyes@panpacificu.edu.ph",
        "scholarship": "4Ps Scholarship",
        "decisions": [
            ("Under Evaluation", "", ""),
            ("Approved", "Household is listed under the 4Ps program.", "100"),
        ],
    },
]


def sample_pdf(title: str) -> bytes:
    safe = title.replace("(", "").replace(")", "")
    content = (
        "BT /F1 18 Tf 60 720 Td (" + safe + ") Tj "
        "0 -30 Td /F1 11 Tf (Sample document created for demonstration purposes.) Tj ET"
    )
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        "<< /Length " + str(len(content)) + " >>\nstream\n" + content + "\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = "%PDF-1.4\n"
    offsets = []
    for index, body in enumerate(objects):
        offsets.append(len(pdf))
        pdf += f"{index + 1} 0 obj\n{body}\nendobj\n"
    start = len(pdf)
    pdf += "xref\n0 " + str(len(objects) + 1) + "\n0000000000 65535 f \n"
    for offset in offsets:
        pdf += str(offset).zfill(10) + " 00000 n \n"
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF"
    return pdf.encode("latin-1")


def _accounts_exist(db: Session) -> bool:
    return db.scalar(select(func.count(User.id))) or 0 > 0


def _find(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email, User.deleted_at.is_(None)))


def _ensure_user(db: Session, spec: dict) -> User:
    existing = _find(db, spec["email"])
    if existing:
        return existing
    user = User(
        email=spec["email"],
        full_name=spec["full_name"],
        role=spec["role"],
        student_id=spec["student_id"],
        program=spec["program"],
        year_level=spec["year_level"],
        password_hash=None if settings.uses_supabase_auth else hash_password(DEMO_PASSWORD),
    )
    db.add(user)
    db.commit()
    return user


def _submit(db: Session, student: User, scholarship: str) -> Application:
    files = {}
    for key in REQUIREMENT_KEYS:
        files[key] = (f"{key}.pdf", sample_pdf(f"{scholarship} - {key}"), "application/pdf")
    return applications_service.create(db, student, {"program": student.program, "yearLevel": student.year_level, "scholarshipType": scholarship}, files)


def _apply_decision(db: Session, actor: User, application: Application, decision: str, remarks: str, discount: str) -> None:
    applications_service.update_status(db, actor, application.id, decision, remarks, discount)


def seed(session: Session) -> None:
    terms_service.current_term(session)

    users = {spec["email"]: _ensure_user(session, spec) for spec in DEMO_USERS}
    actor = users["staff@panpacificu.edu.ph"]

    for spec in DEMO_APPLICATIONS:
        student = users[spec["email"]]
        existing = session.scalar(
            select(Application).where(
                Application.student_user_id == student.id,
                Application.scholarship_type == spec["scholarship"],
                Application.deleted_at.is_(None),
            )
        )
        if existing:
            continue
        application = _submit(session, student, spec["scholarship"])
        for decision, remarks, discount in spec["decisions"]:
            _apply_decision(session, actor, application, decision, remarks, discount)

    if settings.uses_supabase_auth:
        logger.warning(
            "Demo accounts were written to the database, but sign-in uses Supabase Auth. "
            "Create the same accounts in Supabase Auth, or set AUTH_PROVIDER=local for this demo."
        )
    logger.info("Demo accounts ready. Password: %s", DEMO_PASSWORD)


def ensure_demo_accounts(session: Session) -> None:
    """Create the demo data when the database still has no accounts."""

    if not settings.seed_demo_accounts:
        return
    if settings.uses_supabase_storage and not settings.uses_supabase_auth:
        logger.info("Skipping the demo accounts: set AUTH_PROVIDER=supabase or STORAGE_BACKEND=local to seed.")
        return
    if (_accounts_exist(session)) > 0:
        return
    logger.info("SEED_DEMO_ACCOUNTS is on and the database is empty: creating the demo accounts.")
    seed(session)


def main() -> int:
    from .database import SessionLocal, prepare_database

    prepare_database()
    session = SessionLocal()
    try:
        seed(session)
        print(f"Demo accounts ready. Password: {DEMO_PASSWORD}")
        for spec in DEMO_USERS:
            print(f"  {spec['role']:<8} {spec['email']}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
