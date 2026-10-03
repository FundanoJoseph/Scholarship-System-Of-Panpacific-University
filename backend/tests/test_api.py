from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import User

from .conftest import authorization, login, register, requirement_files, submit_application

STATE: dict = {}

ADMIN_EMAIL = "juan.delacruz@panpacificu.edu.ph"
STAFF_EMAIL = "maria.santos@panpacificu.edu.ph"
STUDENT_EMAIL = "ana.reyes@panpacificu.edu.ph"
PASSWORD = "Student#123"


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"] is True


def test_registration_rules(client):
    first = register(client, "Juan Dela Cruz", "1234567", ADMIN_EMAIL)
    assert first["user"]["role"] == "student"
    assert first["access_token"]

    student = register(client, "Ana Reyes", "7654321", STUDENT_EMAIL)
    STATE["student_token"] = student["access_token"]
    STATE["student_id"] = student["user"]["id"]

    duplicate = client.post(
        "/api/auth/register",
        json={
            "fullName": "Juan Dela Cruz",
            "studentId": "1234567",
            "email": ADMIN_EMAIL,
            "program": "BS Computer Science",
            "yearLevel": "3rd Year",
            "password": PASSWORD,
        },
    )
    assert duplicate.status_code == 400
    assert "already exists" in duplicate.json()["detail"]

    weak = client.post(
        "/api/auth/register",
        json={
            "fullName": "Weak Person",
            "studentId": "1111111",
            "email": "weak@panpacificu.edu.ph",
            "program": "BS Accountancy",
            "yearLevel": "1st Year",
            "password": "weakpass",
        },
    )
    assert weak.status_code == 400

    outside = client.post(
        "/api/auth/register",
        json={
            "fullName": "Gmail Person",
            "studentId": "2222222",
            "email": "someone@gmail.com",
            "program": "BS Accountancy",
            "yearLevel": "1st Year",
            "password": "Strong#123",
        },
    )
    assert outside.status_code == 400
    assert "panpacificu.edu.ph" in outside.json()["detail"]


def test_login_and_session(client):
    session = login(client, STUDENT_EMAIL, PASSWORD)
    assert session["user"]["studentId"] == "7654321"
    STATE["student_token"] = session["access_token"]

    assert client.post("/api/auth/login", json={"email": STUDENT_EMAIL, "password": "nope"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401

    me = client.get("/api/auth/me", headers=authorization(session["access_token"]))
    assert me.json()["user"]["email"] == STUDENT_EMAIL

    refreshed = client.post("/api/auth/refresh", json={"refreshToken": session["refresh_token"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]

    assert client.post("/api/auth/refresh", json={"refreshToken": "not-a-token"}).status_code == 401


def test_application_submission(client):
    token = STATE["student_token"]

    missing = client.post(
        "/api/applications",
        data={
            "payload": (
                '{"program": "BS Computer Science", "yearLevel": "3rd Year", '
                '"scholarshipType": "Academic Scholarship"}'
            )
        },
        headers=authorization(token),
    )
    assert missing.status_code == 400
    assert "Missing required document" in missing.json()["detail"]

    application = submit_application(client, token)
    STATE["application_id"] = application["id"]
    assert application["code"].startswith("APP-")
    assert application["status"] == "Submitted"
    assert len(application["documents"]) == 3
    assert [entry["status"] for entry in application["history"]] == ["Submitted"]

    unknown = client.post(
        "/api/applications",
        data={
            "payload": (
                '{"program": "BS Computer Science", "yearLevel": "3rd Year", '
                '"scholarshipType": "Made Up Scholarship"}'
            )
        },
        files=requirement_files(),
        headers=authorization(token),
    )
    assert unknown.status_code == 400

    too_big = requirement_files()
    too_big["copyOfGrades"] = ("big.pdf", b"x" * (6 * 1024 * 1024), "application/pdf")
    oversize = client.post(
        "/api/applications",
        data={
            "payload": (
                '{"program": "BS Computer Science", "yearLevel": "3rd Year", '
                '"scholarshipType": "Academic Scholarship"}'
            )
        },
        files=too_big,
        headers=authorization(token),
    )
    assert oversize.status_code == 413

    mine = client.get("/api/applications?scope=mine", headers=authorization(token)).json()
    assert len(mine["applications"]) == 1

    document = client.get(
        f"/api/applications/{application['id']}/documents/copyOfGrades",
        headers=authorization(token),
    )
    assert document.status_code == 200
    assert document.content.startswith(b"%PDF")

    notifications = client.get("/api/notifications", headers=authorization(token)).json()
    assert "submitted successfully" in notifications["notifications"][0]["message"]
    assert client.get("/api/notifications/unread-count", headers=authorization(token)).json()["count"] == 1

    notification_id = notifications["notifications"][0]["id"]
    assert client.post(f"/api/notifications/{notification_id}/read", headers=authorization(token)).json()["ok"]
    assert client.get("/api/notifications/unread-count", headers=authorization(token)).json()["count"] == 0
    assert client.post("/api/notifications/read-all", headers=authorization(token)).status_code == 200


def test_student_cannot_reach_staff_actions(client):
    token = STATE["student_token"]
    application_id = STATE["application_id"]
    assert client.get("/api/users", headers=authorization(token)).status_code == 403
    assert client.get("/api/applications/history", headers=authorization(token)).status_code == 403
    assert (
        client.post(
            f"/api/applications/{application_id}/status",
            json={"status": "Approved", "remarks": ""},
            headers=authorization(token),
        ).status_code
        == 403
    )
    assert client.delete(f"/api/applications/{application_id}", headers=authorization(token)).status_code == 403
    assert (
        client.post(
            "/api/term",
            json={"trimester": "2nd Trimester", "academicYear": "2027-2028"},
            headers=authorization(token),
        ).status_code
        == 403
    )


def test_first_admin_bootstrap(client):
    session = SessionLocal()
    try:
        person = session.scalar(select(User).where(func.lower(User.email) == ADMIN_EMAIL))
        assert person is not None
        person.role = "admin"
        session.commit()
    finally:
        session.close()

    admin = login(client, ADMIN_EMAIL, PASSWORD)
    assert admin["user"]["role"] == "admin"
    STATE["admin_token"] = admin["access_token"]


def test_admin_creates_staff(client):
    admin_token = STATE["admin_token"]

    created = client.post(
        "/api/users",
        json={"role": "staff", "fullName": "Maria Santos", "email": STAFF_EMAIL, "password": "Staff#1234"},
        headers=authorization(admin_token),
    )
    assert created.status_code == 200, created.text
    assert created.json()["user"]["role"] == "staff"

    duplicate = client.post(
        "/api/users",
        json={"role": "staff", "fullName": "Maria Santos", "email": STAFF_EMAIL, "password": "Staff#1234"},
        headers=authorization(admin_token),
    )
    assert duplicate.status_code == 400

    accounts = client.get("/api/users", headers=authorization(admin_token)).json()["users"]
    assert len(accounts) == 2
    assert {account["role"] for account in accounts} == {"admin", "staff"}

    staff = login(client, STAFF_EMAIL, "Staff#1234")
    STATE["staff_token"] = staff["access_token"]
    assert client.get("/api/users", headers=authorization(staff["access_token"])).status_code == 403


def test_evaluation_rules(client):
    staff_token = STATE["staff_token"]
    application_id = STATE["application_id"]

    jump = client.post(
        f"/api/applications/{application_id}/status",
        json={"status": "Approved", "remarks": "", "discountPercent": "50"},
        headers=authorization(staff_token),
    )
    assert jump.status_code == 400
    assert "cannot move" in jump.json()["detail"]

    rejection = client.post(
        f"/api/applications/{application_id}/status",
        json={"status": "Rejected", "remarks": "", "discountPercent": ""},
        headers=authorization(staff_token),
    )
    assert rejection.status_code == 400

    started = client.post(
        f"/api/applications/{application_id}/status",
        json={"status": "Under Evaluation", "remarks": "", "discountPercent": ""},
        headers=authorization(staff_token),
    )
    assert started.json()["application"]["status"] == "Under Evaluation"

    assert (
        client.patch(
            f"/api/applications/{application_id}/discount",
            json={"discountPercent": "25"},
            headers=authorization(staff_token),
        ).status_code
        == 400
    )

    invalid = client.post(
        f"/api/applications/{application_id}/status",
        json={"status": "Approved", "remarks": "qualified", "discountPercent": "150"},
        headers=authorization(staff_token),
    )
    assert invalid.status_code == 400

    approved = client.post(
        f"/api/applications/{application_id}/status",
        json={"status": "Approved", "remarks": "Qualified for the academic scholarship.", "discountPercent": "75"},
        headers=authorization(staff_token),
    )
    assert approved.json()["application"]["discountPercent"] == "75"

    assert (
        client.post(
            f"/api/applications/{application_id}/status",
            json={"status": "Rejected", "remarks": "changed my mind", "discountPercent": ""},
            headers=authorization(staff_token),
        ).status_code
        == 400
    )

    updated = client.patch(
        f"/api/applications/{application_id}/discount",
        json={"discountPercent": "100"},
        headers=authorization(staff_token),
    )
    assert updated.json()["application"]["discountPercent"] == "100"


def test_student_sees_the_decision(client):
    detail = client.get(
        f"/api/applications/{STATE['application_id']}", headers=authorization(STATE["student_token"])
    ).json()["application"]
    assert detail["status"] == "Approved"
    assert detail["discountPercent"] == "100"
    assert detail["evaluatedBy"] == "Maria Santos"
    assert [entry["status"] for entry in detail["history"]] == ["Submitted", "Under Evaluation", "Approved"]

    messages = [
        item["message"]
        for item in client.get("/api/notifications", headers=authorization(STATE["student_token"])).json()["notifications"]
    ]
    assert any("was Approved" in message for message in messages)

    profile = client.patch(
        "/api/users/me",
        json={"program": "BS Information Technology", "yearLevel": "4th Year"},
        headers=authorization(STATE["student_token"]),
    )
    assert profile.json()["user"]["program"] == "BS Information Technology"


def test_audit_trail(client):
    rows = client.get("/api/applications/history", headers=authorization(STATE["staff_token"])).json()["rows"]
    assert len(rows) == 2
    assert rows[0]["newStatus"] == "Approved"
    assert rows[0]["previousStatus"] == "Under Evaluation"
    assert rows[0]["studentName"] == "Ana Reyes"


def test_term_rollover(client):
    admin_token = STATE["admin_token"]
    moved = client.post(
        "/api/term",
        json={"trimester": "2nd Trimester", "academicYear": "2026-2027"},
        headers=authorization(admin_token),
    )
    assert moved.status_code == 200
    assert moved.json()["archived"] == 1
    assert moved.json()["previousLabel"].startswith("1st Trimester")

    assert (
        client.post(
            "/api/term",
            json={"trimester": "2nd Trimester", "academicYear": "2026-2027"},
            headers=authorization(admin_token),
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/term",
            json={"trimester": "3rd Trimester", "academicYear": "2026-2029"},
            headers=authorization(admin_token),
        ).status_code
        == 400
    )

    term = client.get("/api/term", headers=authorization(STATE["staff_token"])).json()["term"]
    assert term["label"] == "2nd Trimester, AY 2026\u20132027"

    assert client.get("/api/applications?scope=active", headers=authorization(STATE["staff_token"])).json()["applications"] == []
    archived = client.get("/api/applications?scope=all", headers=authorization(STATE["staff_token"])).json()["applications"]
    assert len(archived) == 1 and archived[0]["archived"] is True
    assert archived[0]["term"].startswith("1st Trimester")

    assert (
        client.post(
            f"/api/applications/{STATE['application_id']}/status",
            json={"status": "Under Evaluation", "remarks": ""},
            headers=authorization(STATE["staff_token"]),
        ).status_code
        == 400
    )


def test_password_flows(client):
    token = STATE["student_token"]
    wrong = client.post(
        "/api/auth/change-password",
        json={"currentPassword": "wrong", "newPassword": "Ana#99999"},
        headers=authorization(token),
    )
    assert wrong.status_code == 400

    changed = client.post(
        "/api/auth/change-password",
        json={"currentPassword": PASSWORD, "newPassword": "Ana#99999"},
        headers=authorization(token),
    )
    assert changed.status_code == 200
    assert login(client, STUDENT_EMAIL, "Ana#99999")["access_token"]

    assert client.post("/api/auth/password-reset/request", json={"email": "nobody@panpacificu.edu.ph"}).status_code == 400

    requested = client.post("/api/auth/password-reset/request", json={"email": STUDENT_EMAIL})
    reset_token = requested.json()["resetToken"]
    assert reset_token

    confirmed = client.post(
        "/api/auth/password-reset/confirm", json={"token": reset_token, "newPassword": "Reset#12345"}
    )
    assert confirmed.status_code == 200
    assert (
        client.post("/api/auth/password-reset/confirm", json={"token": reset_token, "newPassword": "Reset#99999"}).status_code
        == 400
    )
    STATE["student_token"] = login(client, STUDENT_EMAIL, "Reset#12345")["access_token"]


def test_soft_delete_keeps_the_audit_trail(client):
    application_id = STATE["application_id"]
    staff_token = STATE["staff_token"]

    deleted = client.delete(f"/api/applications/{application_id}", headers=authorization(staff_token))
    assert deleted.status_code == 200
    assert deleted.json()["application"]["id"] == application_id

    assert client.get("/api/applications?scope=all", headers=authorization(staff_token)).json()["applications"] == []
    assert client.get(f"/api/applications/{application_id}", headers=authorization(staff_token)).status_code == 404
    assert (
        client.get(
            f"/api/applications/{application_id}/documents/copyOfGrades", headers=authorization(staff_token)
        ).status_code
        == 404
    )
    assert client.get("/api/applications?scope=mine", headers=authorization(STATE["student_token"])).json()["applications"] == []

    rows = client.get("/api/applications/history", headers=authorization(staff_token)).json()["rows"]
    assert len(rows) == 2
    assert all(row["deleted"] for row in rows)

    session = SessionLocal()
    try:
        person = session.scalar(select(User).where(func.lower(User.email) == STUDENT_EMAIL))
        assert person.deleted_at is None
    finally:
        session.close()
