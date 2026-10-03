"""Fill a development database with accounts and sample applications.

It uses the running API the same way the browser does (register.html, the Add
Account page, the scholarship application form), then promotes the first admin
with the same database update that promote_admin.py performs.

    python backend/scripts/seed_dev.py
    python backend/scripts/seed_dev.py --base-url http://127.0.0.1:8000/api

The accounts and applications it creates live only in your development
database (backend/var/dev.db by default). Delete that file to start over.
"""

import argparse
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.database import SessionLocal, prepare_database  # noqa: E402
from app.models import User  # noqa: E402

PASSWORD = "Panpacific#2026"
ADMIN_EMAIL = "admin@panpacificu.edu.ph"
STAFF_EMAIL = "staff@panpacificu.edu.ph"
STUDENTS = [
    ("Juan Dela Cruz", "1234567", "juan.delacruz@panpacificu.edu.ph", "BS Computer Science", "3rd Year"),
    ("Ana Reyes", "7654321", "ana.reyes@panpacificu.edu.ph", "BS Accountancy", "2nd Year",),
]
REQUIREMENTS = ("copyOfGrades", "letterOfIntent", "notarizedAgreement")


def sample_pdf(title: str) -> bytes:
    text = title.replace("(", "").replace(")", "")
    content = (
        "BT /F1 18 Tf 60 720 Td (" + text + ") Tj "
        "0 -30 Td /F1 11 Tf (Sample document created by seed_dev.py for local testing.) Tj ET"
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


def uploads(label: str) -> dict:
    files = {}
    for key in REQUIREMENTS:
        name = f"{key}.pdf"
        files[key] = (name, sample_pdf(f"{label} - {key}"), "application/pdf")
    return files


def register(client: httpx.Client, person: dict, password: str) -> str:
    response = client.post("/auth/register", json={**person, "password": password})
    if response.status_code == 200:
        return response.json()["access_token"]
    login = client.post("/auth/login", json={"email": person["email"], "password": password})
    if login.status_code != 200:
        raise SystemExit(f"Could not create or log in {person['email']}: {response.text} {login.text}")
    return login.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def submit(client: httpx.Client, token: str, scholarship: str) -> dict:
    response = client.post(
        "/applications",
        data={
            "payload": (
                '{"program": "BS Computer Science", "yearLevel": "3rd Year", '
                f'"scholarshipType": "{scholarship}"}}'
            )
        },
        files=uploads(scholarship),
        headers=auth(token),
    )
    if response.status_code != 200:
        raise SystemExit(f"Could not submit an application: {response.text}")
    return response.json()["application"]


def promote(email: str, role: str = "admin") -> str:
    prepare_database()
    session = SessionLocal()
    try:
        person = session.scalar(
            select(User).where(func.lower(User.email) == email.lower(), User.deleted_at.is_(None))
        )
        if person is None:
            raise SystemExit(f"{email} was not found in the database.")
        previous = person.role
        person.role = role
        session.commit()
        return f"{previous} -> {role}"
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api")
    parser.add_argument("--password", default=PASSWORD)
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=60)
    try:
        health = client.get("/health")
    except httpx.HTTPError:
        raise SystemExit("The API is not running. Start it first: python -m uvicorn app.main:app --port 8000")
    if health.status_code != 200:
        raise SystemExit(f"The API answered with {health.status_code}. Check the server logs.")

    print("Creating accounts...")
    admin_token = register(
        client,
        {"fullName": "CSS Administrator", "studentId": "0000001", "email": ADMIN_EMAIL,
         "program": "CSS Office", "yearLevel": "1st Year"},
        args.password,
    )
    print(f"  {ADMIN_EMAIL} (student)")

    print("Promoting the first admin:", promote(ADMIN_EMAIL))
    admin_token = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": args.password}).json()["access_token"]

    staff = client.post(
        "/users",
        json={"role": "staff", "fullName": "Reyna Cruz", "email": STAFF_EMAIL, "password": args.password},
        headers=auth(admin_token),
    )
    if staff.status_code == 200:
        print(f"  {STAFF_EMAIL} (staff) created from the Account Management page flow")
    else:
        print(f"  {STAFF_EMAIL} already existed ({staff.json().get('detail')})")
    staff_token = client.post("/auth/login", json={"email": STAFF_EMAIL, "password": args.password}).json()["access_token"]

    print("Creating students...")
    tokens = {}
    for name, student_id, email, program, year_level in STUDENTS:
        tokens[email] = register(
            client,
            {"fullName": name, "studentId": student_id, "email": email, "program": program, "yearLevel": year_level},
            args.password,
        )
        print(f"  {name} <{email}>")

    print("Submitting applications...")
    juan = STUDENTS[0][2]
    ana = STUDENTS[1][2]
    first = submit(client, tokens[juan], "Academic Scholarship")

    second = submit(client, tokens[ana], "Entrance Exam Scholarship")
    client.post(
        f"/applications/{second['id']}/status",
        json={"status": "Under Evaluation", "remarks": "", "discountPercent": ""},
        headers=auth(staff_token),
    )
    client.post(
        f"/applications/{second['id']}/status",
        json={"status": "Rejected", "remarks": "Entrance examination score is below the qualifying cut-off.", "discountPercent": ""},
        headers=auth(staff_token),
    )

    third = submit(client, tokens[ana], "4Ps Scholarship")
    client.post(
        f"/applications/{third['id']}/status",
        json={"status": "Under Evaluation", "remarks": "", "discountPercent": ""},
        headers=auth(staff_token),
    )
    client.post(
        f"/applications/{third['id']}/status",
        json={"status": "Approved", "remarks": "Household is listed under the 4Ps program.", "discountPercent": "100"},
        headers=auth(staff_token),
    )

    print(f"  {first['code']} Academic Scholarship (Juan)   - Submitted")
    print(f"  {second['code']} Entrance Exam Scholarship (Ana) - Rejected")
    print(f"  {third['code']} 4Ps Scholarship (Ana)          - Approved, 100% discount")

    print()
    print("Sign in with any of these (development database only):")
    print(f"  Admin : {ADMIN_EMAIL} / {args.password}")
    print(f"  Staff : {STAFF_EMAIL} / {args.password}")
    for name, _, email, _, _ in STUDENTS:
        print(f"  Student: {email} / {args.password}")
    print()
    print("Change the passwords from the app, or delete backend/var/dev.db to start over.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
