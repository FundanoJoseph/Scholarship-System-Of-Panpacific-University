import os
import tempfile
from pathlib import Path

TEST_ROOT = Path(tempfile.mkdtemp(prefix="sams-tests-"))

os.environ["ENVIRONMENT"] = "development"
os.environ["AUTH_PROVIDER"] = "local"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["SERVE_FRONTEND"] = "false"
os.environ["CORS_ORIGINS"] = ""
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_ROOT / 'test.db'}"
os.environ["UPLOAD_DIR"] = str(TEST_ROOT / "uploads")
os.environ["JWT_SECRET"] = "test-secret-value-used-only-by-the-test-suite"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


def authorization(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def pdf_bytes(label: str = "document") -> bytes:
    return (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"trailer\n<< /Size 1 >>\n%%EOF\n" + label.encode()
    )


def requirement_files() -> dict:
    return {
        "copyOfGrades": ("grades.pdf", pdf_bytes("grades"), "application/pdf"),
        "letterOfIntent": ("letter.pdf", pdf_bytes("letter"), "application/pdf"),
        "notarizedAgreement": ("agreement.pdf", pdf_bytes("agreement"), "application/pdf"),
    }


def register(client, full_name, student_id, email, password="Student#123"):
    response = client.post(
        "/api/auth/register",
        json={
            "fullName": full_name,
            "studentId": student_id,
            "email": email,
            "program": "BS Computer Science",
            "yearLevel": "3rd Year",
            "password": password,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def login(client, email, password):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def submit_application(client, token, scholarship="Academic Scholarship"):
    response = client.post(
        "/api/applications",
        data={
            "payload": (
                '{"program": "BS Computer Science", "yearLevel": "3rd Year", '
                f'"scholarshipType": "{scholarship}"}}'
            )
        },
        files=requirement_files(),
        headers=authorization(token),
    )
    assert response.status_code == 200, response.text
    return response.json()["application"]
