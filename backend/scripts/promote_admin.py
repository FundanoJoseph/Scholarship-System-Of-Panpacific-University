"""Give an existing account the admin (or staff) role.

Normal flow for the very first administrator:

    1. Register a normal account through template/register.html
       (that creates a student row in the users table).
    2. Run this script for that email address.
    3. Log in again - the Admin / Staff side of the app is now visible,
       and more staff or admin accounts can be created from Account Management.

Usage:
    python backend/scripts/promote_admin.py --list
    python backend/scripts/promote_admin.py you@panpacificu.edu.ph
    python backend/scripts/promote_admin.py you@panpacificu.edu.ph --role staff
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.database import SessionLocal, prepare_database  # noqa: E402
from app.models import ROLES, User  # noqa: E402


def list_accounts(session) -> None:
    people = session.scalars(
        select(User).where(User.deleted_at.is_(None)).order_by(User.role, User.created_at)
    ).all()
    if not people:
        print("No accounts yet. Register one through the app first.")
        return
    print(f"{'email':<40} {'role':<9} name")
    print("-" * 70)
    for person in people:
        print(f"{person.email:<40} {person.role:<9} {person.full_name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email", nargs="?", help="email address of an existing account")
    parser.add_argument("--role", default="admin", choices=sorted(ROLES), help="role to apply (default: admin)")
    parser.add_argument("--list", action="store_true", help="list the accounts in the database")
    args = parser.parse_args()

    prepare_database()
    session = SessionLocal()
    try:
        if args.list or not args.email:
            list_accounts(session)
            return 0 if args.list else 1

        person = session.scalar(
            select(User).where(
                func.lower(User.email) == args.email.strip().lower(),
                User.deleted_at.is_(None),
            )
        )
        if person is None:
            print(f"No account found for {args.email}. Register it through the app first.")
            return 1

        previous = person.role
        person.role = args.role
        session.commit()
        print(f"{person.email}: {previous} -> {person.role}. Log in again to see the change.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
