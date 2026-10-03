from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import TermIn
from ..security import get_current_user, require_roles
from ..services import terms

router = APIRouter(prefix="/term", tags=["term"])


@router.get("")
def read_term(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"term": terms.get_public(db)}


@router.post("")
def write_term(
    payload: TermIn,
    actor: User = Depends(require_roles("staff", "admin")),
    db: Session = Depends(get_db),
):
    result = terms.set_current_term(db, actor, payload.trimester, payload.academicYear)
    return {"term": terms.get_public(db), **result}
