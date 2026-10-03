from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import Application, Term, User, utcnow
from ..serializers import term_public
from ..validation import bad_request, check_academic_year, check_trimester, term_label

DEFAULT_TRIMESTER = "1st Trimester"
DEFAULT_ACADEMIC_YEAR = "2026\u20132027"


def current_term(db: Session) -> Term:
    term = db.scalar(select(Term).where(Term.is_current.is_(True), Term.deleted_at.is_(None)))
    if term:
        return term

    label = term_label(DEFAULT_TRIMESTER, DEFAULT_ACADEMIC_YEAR)
    term = Term(
        trimester=DEFAULT_TRIMESTER,
        academic_year=DEFAULT_ACADEMIC_YEAR,
        label=label,
        is_current=True,
    )
    db.add(term)
    db.commit()
    return term


def get_public(db: Session) -> dict:
    return term_public(current_term(db))


def set_current_term(db: Session, actor: User, trimester: str, academic_year: str) -> dict:
    trimester = check_trimester(trimester)
    academic_year = check_academic_year(academic_year)
    new_label = term_label(trimester, academic_year)

    current = current_term(db)
    previous_label = current.label
    if new_label == previous_label:
        raise bad_request(f"The system is already on {new_label}. Nothing was changed.")

    archived = db.execute(
        update(Application)
        .where(Application.archived.is_(False), Application.deleted_at.is_(None))
        .values(archived=True, term_label=previous_label, updated_at=utcnow())
    ).rowcount

    current.is_current = False
    db.flush()

    db.add(
        Term(
            trimester=trimester,
            academic_year=academic_year,
            label=new_label,
            is_current=True,
            created_by=actor.id,
        )
    )
    db.commit()
    return {
        "label": new_label,
        "previousLabel": previous_label,
        "archived": int(archived or 0),
    }
