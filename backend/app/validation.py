import re
from typing import Any

from fastapi import HTTPException, status

from .config import settings

SCHOLARSHIP_TYPES = (
    "Academic Scholarship",
    "Entrance Exam Scholarship",
    "4Ps Scholarship",
    "Urdanetarian Scholarship",
    "RPSEA Scholarship",
    "SOC Scholarship",
    "BSA Scholarship",
    "New Program Scholarship",
)

TRIMESTERS = ("1st Trimester", "2nd Trimester", "3rd Trimester")
YEAR_LEVELS = ("1st Year", "2nd Year", "3rd Year", "4th Year", "Irregular")

REQUIREMENT_KEYS = ("copyOfGrades", "letterOfIntent", "notarizedAgreement")
REQUIREMENT_LABELS = {
    "copyOfGrades": "Copy of Grades",
    "letterOfIntent": "Letter of Intent",
    "notarizedAgreement": "Notarized Scholarship Agreement",
}

LETTERS_ONLY_RE = re.compile(r"^[A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF][A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF .,'&-]*$")
STUDENT_ID_RE = re.compile(r"^[0-9]{7}$")
ACADEMIC_YEAR_RE = re.compile(r"^(\d{4})\s*[-\/]\s*(\d{4})$")


def bad_request(message: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, message)


def required(value: Any, label: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise bad_request(f"{label} is required.")
    return text


def check_letters_only(value: Any, label: str) -> str:
    text = required(value, label)
    if not LETTERS_ONLY_RE.match(text):
        raise bad_request(f"{label} must contain letters only. Numbers are not allowed.")
    return text


def check_student_id(value: Any) -> str:
    text = required(value, "Student ID")
    if not STUDENT_ID_RE.match(text):
        raise bad_request("Student ID must be exactly 7 digits (example: 0000000).")
    return text


def check_year_level(value: Any) -> str:
    text = required(value, "Year level")
    if text not in YEAR_LEVELS:
        raise bad_request("Please choose a valid year level.")
    return text


def normalize_academic_year(value: Any) -> str:
    match = ACADEMIC_YEAR_RE.match(str(value or "").strip())
    if not match:
        return str(value or "").strip()
    return f"{match[1]}\u2013{match[2]}"


def check_academic_year(value: Any) -> str:
    text = required(value, "Academic year")
    match = ACADEMIC_YEAR_RE.match(text)
    if not match:
        raise bad_request("Academic year must be two years like 2026-2027.")
    start, end = int(match[1]), int(match[2])
    if end != start + 1:
        raise bad_request(f"The second year must follow the first (you typed {start}-{end}; did you mean {start}-{start + 1}?).")
    if start < 2000 or start > 2100:
        raise bad_request("Please use a realistic academic year (between 2000 and 2100).")
    return normalize_academic_year(text)


def check_trimester(value: Any) -> str:
    text = required(value, "Trimester")
    if text not in TRIMESTERS:
        raise bad_request("Please choose the 1st, 2nd or 3rd Trimester.")
    return text


def check_scholarship_type(value: Any) -> str:
    text = required(value, "Scholarship type")
    if text not in SCHOLARSHIP_TYPES:
        raise bad_request("Please choose a scholarship program from the list.")
    return text


def term_label(trimester: str, academic_year: str) -> str:
    return f"{trimester}, AY {academic_year}"


def check_email(value: Any) -> str:
    email = required(value, "University email").lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise bad_request("Please enter a valid email address.")
    domain = settings.university_email_domain.strip().lower()
    if domain and not email.endswith(domain):
        raise bad_request(f"Only {domain} email addresses are accepted.")
    return email


def check_discount(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if text == "":
        return ""
    try:
        number = float(text)
    except ValueError as error:
        raise bad_request("Discount percentage must be a number between 0 and 100.") from error
    if number != number or number < 0 or number > 100:
        raise bad_request("Discount percentage must be a number between 0 and 100.")
    return str(int(number)) if number == int(number) else str(number)
