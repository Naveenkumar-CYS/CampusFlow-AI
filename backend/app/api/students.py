from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.rbac import Role, enforce_own_student_record, require_roles
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.student import StudentCreate, StudentRead, StudentUpdate
from app.services import student as student_service

router = APIRouter(prefix="/students", tags=["students"])

# Staff roles that may read the student directory / any single student
# record. STUDENT is deliberately excluded here — students may only read
# their own record, which is enforced separately (object-level check).
_DIRECTORY_READERS = {Role.ADMIN, Role.FACULTY, Role.ACCOUNTS, Role.WARDEN, Role.EXAM_OFFICER}


@router.post(
    "",
    response_model=StudentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)) -> StudentRead:
    try:
        student = student_service.create_student(db, payload)
    except student_service.DuplicateStudentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return student


@router.get("/{student_id}", response_model=StudentRead)
def get_student(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_DIRECTORY_READERS, Role.STUDENT)),
) -> StudentRead:
    # Object-level check: a STUDENT may only fetch their own record. Staff
    # roles pass straight through.
    enforce_own_student_record(
        current_user, db, staff_roles=_DIRECTORY_READERS, target_student_code=student_id
    )
    student = student_service.get_student(db, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student


@router.get(
    "",
    response_model=list[StudentRead],
    dependencies=[Depends(require_roles(*_DIRECTORY_READERS))],
)
def list_students(db: Session = Depends(get_db)) -> list[StudentRead]:
    return student_service.list_students(db)


@router.patch(
    "/{student_id}",
    response_model=StudentRead,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
def update_student(
    student_id: str, payload: StudentUpdate, db: Session = Depends(get_db)
) -> StudentRead:
    student = student_service.update_student(db, student_id, payload)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student


@router.delete(
    "/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
def delete_student(student_id: str, db: Session = Depends(get_db)) -> None:
    try:
        deleted = student_service.delete_student(db, student_id)
    except student_service.StudentHasAdmissionsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
