"""Check the backend in Supabase mode against a local stand-in.

    python scripts/verify_supabase_mode.py                 # both signing modes
    python scripts/verify_supabase_mode.py --signing hs256

The stand-in (scripts/mock_supabase.py) speaks the same Auth and Storage
endpoints as Supabase, so this proves sign-in, tokens, roles, document upload,
password changes and the audit trail work before a real project is wired up.
Both signing styles are covered: rs256 (JWKS, the default for new Supabase
projects) and hs256 (the legacy shared secret).
"""

import argparse
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import time

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PYTHON = sys.executable
SHARED_SECRET = "mock-supabase-shared-secret-value"
ANON_KEY = "anon-key-for-tests"
SERVICE_KEY = "service-key-for-tests"

results: list[tuple[str, bool, str]] = []


def check(label: str, condition, extra: str = "") -> None:
    results.append((label, bool(condition), extra))
    print(("PASS " if condition else "FAIL ") + label + (f"  [{extra}]" if extra and not condition else ""))


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_for(url: str, timeout: float = 45) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(url, timeout=3)
            return True
        except httpx.HTTPError:
            time.sleep(0.4)
    return False


def start_mock(port: int, signing: str) -> subprocess.Popen:
    environment = dict(os.environ)
    environment.update({"MOCK_SIGNING": signing, "MOCK_SHARED_SECRET": SHARED_SECRET})
    process = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "mock_supabase:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(SCRIPTS),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if not wait_for(f"http://127.0.0.1:{port}/auth/v1/.well-known/jwks.json"):
        raise SystemExit("The stand-in Supabase server did not start.")
    return process


def start_api(workdir: str, mock_port: int, api_port: int, jwt_secret: str) -> subprocess.Popen:
    environment = dict(os.environ)
    environment.update(
        {
            "ENVIRONMENT": "production",
            "AUTH_PROVIDER": "supabase",
            "STORAGE_BACKEND": "supabase",
            "SUPABASE_URL": f"http://127.0.0.1:{mock_port}",
            "SUPABASE_ANON_KEY": ANON_KEY,
            "SUPABASE_SERVICE_KEY": SERVICE_KEY,
            "SUPABASE_JWT_SECRET": jwt_secret,
            "STORAGE_BUCKET": "scholarship-documents",
            "DATABASE_URL": f"sqlite:///{workdir}/app.db",
            "UPLOAD_DIR": f"{workdir}/uploads",
            "JWT_SECRET": "local-fallback-secret-used-by-this-check",
            "SEED_DEMO_ACCOUNTS": "false",
        }
    )
    process = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(api_port)],
        cwd=str(ROOT),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if not wait_for(f"http://127.0.0.1:{api_port}/api/health"):
        raise SystemExit("The API did not start in Supabase mode.")
    return process


def promote(email: str, workdir: str) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment.update({"DATABASE_URL": f"sqlite:///{workdir}/app.db", "AUTH_PROVIDER": "supabase"})
    return subprocess.run(
        [PYTHON, "scripts/promote_admin.py", email],
        cwd=str(ROOT),
        env=environment,
        capture_output=True,
        text=True,
    )


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def pdf(label: str = "doc") -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n" + label.encode()


def requirement_files() -> dict:
    return {
        "copyOfGrades": ("grades.pdf", pdf("grades"), "application/pdf"),
        "letterOfIntent": ("letter.pdf", pdf("letter"), "application/pdf"),
        "notarizedAgreement": ("agreement.pdf", pdf("agreement"), "application/pdf"),
    }


def run_suite(client: httpx.Client, state_client: httpx.Client, mock_base: str, workdir: str, label: str) -> None:
    admin_email = "juan.delacruz@panpacificu.edu.ph"
    student_email = "ana.reyes@panpacificu.edu.ph"

    response = client.post(
        "/auth/register",
        json={
            "fullName": "Juan Dela Cruz",
            "studentId": "1234567",
            "email": admin_email,
            "program": "BS Computer Science",
            "yearLevel": "3rd Year",
            "password": "Student#123",
        },
    )
    check(f"[{label}] register creates the account and a local row", response.status_code == 200, response.text[:300])
    check(
        f"[{label}] register returns a Supabase session",
        bool(response.json().get("access_token")) and bool(response.json().get("refresh_token")),
        response.text[:200],
    )
    state = state_client.get(f"{mock_base}/__state").json()
    check(
        f"[{label}] the auth service keeps the full name",
        state["users"][0]["metadata"].get("full_name") == "Juan Dela Cruz",
        str(state["users"]),
    )

    response = client.post(
        "/auth/register",
        json={
            "fullName": "Ana Reyes",
            "studentId": "7654321",
            "email": student_email,
            "program": "BS Accountancy",
            "yearLevel": "2nd Year",
            "password": "Ana#12345",
        },
    )
    check(f"[{label}] second registration", response.status_code == 200, response.text[:300])

    duplicate = client.post(
        "/auth/register",
        json={
            "fullName": "Ana Reyes",
            "studentId": "7654321",
            "email": student_email,
            "program": "BS Accountancy",
            "yearLevel": "2nd Year",
            "password": "Ana#12345",
        },
    )
    check(
        f"[{label}] duplicate email blocked",
        duplicate.status_code == 400 and "already exists" in duplicate.json()["detail"],
        duplicate.text[:300],
    )

    response = client.post("/auth/login", json={"email": student_email, "password": "Ana#12345"})
    check(f"[{label}] login through the auth service", response.status_code == 200, response.text[:300])
    student_token = response.json()["access_token"]
    refresh_token = response.json()["refresh_token"]

    check(f"[{label}] wrong password rejected", client.post("/auth/login", json={"email": student_email, "password": "nope"}).status_code == 401)

    response = client.get("/auth/me", headers=auth(student_token))
    check(
        f"[{label}] token verified and linked to the local row",
        response.status_code == 200 and response.json()["user"]["studentId"] == "7654321",
        response.text[:300],
    )
    check(f"[{label}] forged token rejected", client.get("/auth/me", headers=auth("not.a.real.token")).status_code == 401)

    response = client.post("/auth/refresh", json={"refreshToken": refresh_token})
    check(f"[{label}] refresh session", response.status_code == 200 and response.json()["access_token"], response.text[:300])
    student_token = response.json()["access_token"]

    response = client.post(
        "/applications",
        data={
            "payload": (
                '{"program": "BS Computer Science", "yearLevel": "3rd Year", '
                '"scholarshipType": "Academic Scholarship"}'
            )
        },
        files=requirement_files(),
        headers=auth(student_token),
    )
    check(f"[{label}] application submitted (documents into storage)", response.status_code == 200, response.text[:400])
    application = response.json()["application"] if response.status_code == 200 else {}
    application_id = application.get("id", "")
    stored = state_client.get(f"{mock_base}/__state").json()["objects"]
    check(f"[{label}] three documents in the bucket", len([item for item in stored if application_id in item]) == 3, str(stored))

    response = client.get(f"/applications/{application_id}/documents/copyOfGrades", headers=auth(student_token))
    check(f"[{label}] document download from storage", response.status_code == 200 and response.content.startswith(b"%PDF"), response.text[:200])

    response = client.patch("/users/me", json={"program": "BS Information Technology", "yearLevel": "4th Year"}, headers=auth(student_token))
    check(f"[{label}] profile update", response.status_code == 200 and response.json()["user"]["program"] == "BS Information Technology", response.text[:300])

    promoted = promote(admin_email, workdir)
    check(f"[{label}] first admin bootstrap", promoted.returncode == 0 and "admin" in promoted.stdout, promoted.stdout + promoted.stderr)

    admin = client.post("/auth/login", json={"email": admin_email, "password": "Student#123"})
    check(f"[{label}] admin can log in after promotion", admin.status_code == 200 and admin.json()["user"]["role"] == "admin", admin.text[:300])
    admin_token = admin.json()["access_token"]

    response = client.post(
        "/users",
        json={"role": "staff", "fullName": "Maria Santos", "email": "maria.santos@panpacificu.edu.ph", "password": "Staff#1234"},
        headers=auth(admin_token),
    )
    check(f"[{label}] admin creates a staff account", response.status_code == 200 and response.json()["user"]["role"] == "staff", response.text[:300])

    staff = client.post("/auth/login", json={"email": "maria.santos@panpacificu.edu.ph", "password": "Staff#1234"})
    check(f"[{label}] the new staff member can log in", staff.status_code == 200, staff.text[:300])
    staff_token = staff.json()["access_token"]
    check(f"[{label}] staff cannot manage accounts", client.get("/users", headers=auth(staff_token)).status_code == 403)

    response = client.post(
        f"/applications/{application_id}/status",
        json={"status": "Under Evaluation", "remarks": "", "discountPercent": ""},
        headers=auth(staff_token),
    )
    check(f"[{label}] staff starts the evaluation", response.status_code == 200, response.text[:300])

    response = client.post(
        f"/applications/{application_id}/status",
        json={"status": "Approved", "remarks": "Qualified.", "discountPercent": "75"},
        headers=auth(staff_token),
    )
    check(f"[{label}] staff approves with a discount", response.status_code == 200 and response.json()["application"]["discountPercent"] == "75", response.text[:300])

    detail = client.get(f"/applications/{application_id}", headers=auth(student_token)).json()["application"]
    check(f"[{label}] student sees the decision", detail["status"] == "Approved" and detail["evaluatedBy"] == "Maria Santos", str(detail)[:200])
    check(f"[{label}] history is complete", [entry["status"] for entry in detail["history"]] == ["Submitted", "Under Evaluation", "Approved"], str(detail["history"]))

    rows = client.get("/applications/history", headers=auth(staff_token)).json()["rows"]
    check(f"[{label}] audit trail", len(rows) == 2, str(rows)[:200])

    wrong = client.post("/auth/change-password", json={"currentPassword": "wrong-one", "newPassword": "Ana#99999"}, headers=auth(student_token))
    check(f"[{label}] wrong current password blocked", wrong.status_code == 400, wrong.text[:200])

    changed = client.post("/auth/change-password", json={"currentPassword": "Ana#12345", "newPassword": "Ana#99999"}, headers=auth(student_token))
    check(f"[{label}] password change goes through the auth service", changed.status_code == 200, changed.text[:200])
    check(f"[{label}] login with the new password", client.post("/auth/login", json={"email": student_email, "password": "Ana#99999"}).status_code == 200)
    check(f"[{label}] the old password no longer works", client.post("/auth/login", json={"email": student_email, "password": "Ana#12345"}).status_code == 401)

    reset = client.post("/auth/password-reset/request", json={"email": student_email})
    check(f"[{label}] reset request reaches the recovery endpoint", reset.status_code == 200 and reset.json().get("emailed") is True, reset.text[:300])

    check(f"[{label}] logout accepted", client.post("/auth/logout", headers=auth(student_token)).status_code == 200)

    deleted = client.delete(f"/applications/{application_id}", headers=auth(staff_token))
    check(f"[{label}] staff deletes the application", deleted.status_code == 200, deleted.text[:300])
    remaining = state_client.get(f"{mock_base}/__state").json()["objects"]
    check(f"[{label}] documents removed from the bucket", not [item for item in remaining if application_id in item], str(remaining))

    rows = client.get("/applications/history", headers=auth(staff_token)).json()["rows"]
    check(f"[{label}] audit trail survives the delete", len(rows) == 2 and all(row["deleted"] for row in rows), str(rows)[:200])

    term = client.get("/term", headers=auth(staff_token))
    check(f"[{label}] term endpoint works with a verified token", term.status_code == 200, term.text[:200])


def run_mode(signing: str) -> None:
    mock_port = free_port()
    api_port = free_port()
    workdir = tempfile.mkdtemp(prefix=f"sams-supabase-{signing}-")
    mock = start_mock(mock_port, signing)
    api = start_api(workdir, mock_port, api_port, SHARED_SECRET if signing == "hs256" else "")
    mock_base = f"http://127.0.0.1:{mock_port}"
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{api_port}/api", timeout=40) as client:
            with httpx.Client(timeout=20) as state_client:
                health = client.get("/health").json()
                check(
                    f"[{signing}] health reports the Supabase backends",
                    health["authProvider"] == "supabase" and health["storageBackend"] == "supabase",
                    str(health),
                )
                run_suite(client, state_client, mock_base, workdir, signing)
    finally:
        api.terminate()
        log = api.communicate(timeout=30)[0]
        mock.terminate()
        mock.communicate(timeout=30)
        problems = [line for line in log.splitlines() if "ERROR" in line or "Traceback" in line]
        if problems:
            print(f"--- API log ({signing}) ---")
            print("\n".join(problems[:20]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--signing", choices=["rs256", "hs256"], help="only check this signing style")
    args = parser.parse_args()

    for signing in [args.signing] if args.signing else ["rs256", "hs256"]:
        run_mode(signing)

    failed = [item for item in results if not item[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    for label, _, extra in failed:
        print("FAILED:", label, extra)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
