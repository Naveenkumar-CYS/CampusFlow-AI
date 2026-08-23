import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.rbac import (
    Role,
    enforce_own_student_filter,
    enforce_own_student_record,
    require_roles,
)
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.examination import (
    ExamCreate,
    ExamRead,
    ExamUpdate,
    RegistrationCreate,
    RegistrationRead,
)
from app.services import examination as exam_service

router = APIRouter(prefix="/examinations", tags=["examinations"])

_EXAM_STAFF = {Role.ADMIN, Role.EXAM_OFFICER}
# Exam definitions (code/subject/schedule) are public campus info once
# created, so any authenticated role may read them.
_ANY_AUTHENTICATED = {
    Role.ADMIN, Role.EXAM_OFFICER, Role.STUDENT, Role.FACULTY, Role.ACCOUNTS, Role.WARDEN,
}


# ----------------------------------------------------------------------- Exam


@router.post(
    "", response_model=ExamRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*_EXAM_STAFF))],
)
def create_exam(payload: ExamCreate, db: Session = Depends(get_db)) -> ExamRead:
    try:
        return exam_service.create_exam(db, payload)
    except exam_service.DuplicateExamError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "/{exam_code}", response_model=ExamRead,
    dependencies=[Depends(require_roles(*_ANY_AUTHENTICATED))],
)
def get_exam(exam_code: str, db: Session = Depends(get_db)) -> ExamRead:
    exam = exam_service.get_exam(db, exam_code)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    return exam


@router.get(
    "", response_model=list[ExamRead],
    dependencies=[Depends(require_roles(*_ANY_AUTHENTICATED))],
)
def list_exams(db: Session = Depends(get_db)) -> list[ExamRead]:
    return exam_service.list_exams(db)


@router.patch(
    "/{exam_code}", response_model=ExamRead,
    dependencies=[Depends(require_roles(*_EXAM_STAFF))],
)
def update_exam(exam_code: str, payload: ExamUpdate, db: Session = Depends(get_db)) -> ExamRead:
    exam = exam_service.update_exam(db, exam_code, payload)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    return exam


@router.delete(
    "/{exam_code}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(*_EXAM_STAFF))],
)
def delete_exam(exam_code: str, db: Session = Depends(get_db)) -> None:
    try:
        deleted = exam_service.delete_exam(db, exam_code)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete exam with existing registrations",
        ) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")


# ---------------------------------------------------------------- Registration


@router.post(
    "/{exam_code}/register", response_model=RegistrationRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*_EXAM_STAFF))],
)
def register_student(
    exam_code: str, payload: RegistrationCreate, db: Session = Depends(get_db)
) -> RegistrationRead:
    try:
        return exam_service.register_student(db, exam_code, payload)
    except exam_service.ExamNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except exam_service.StudentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except exam_service.DuplicateRegistrationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{exam_code}/registrations", response_model=list[RegistrationRead])
def list_registrations(
    exam_code: str,
    student_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_EXAM_STAFF, Role.STUDENT)),
) -> list[RegistrationRead]:
    enforce_own_student_filter(
        current_user, db, staff_roles=_EXAM_STAFF, requested_student_code=student_id
    )
    try:
        return exam_service.list_registrations(db, exam_code, student_id=student_id)
    except exam_service.ExamNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except exam_service.StudentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{exam_code}/registrations/{registration_id}", response_model=RegistrationRead)
def get_registration(
    exam_code: str,
    registration_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_EXAM_STAFF, Role.STUDENT)),
) -> RegistrationRead:
    registration = exam_service.get_registration(db, registration_id)
    if registration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration not found")
    enforce_own_student_record(
        current_user, db, staff_roles=_EXAM_STAFF, target_student_pk=registration.student_id
    )
    return registration


@router.delete(
    "/{exam_code}/registrations/{registration_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(*_EXAM_STAFF))],
)
def delete_registration(
    exam_code: str, registration_id: uuid.UUID, db: Session = Depends(get_db)
) -> None:
    deleted = exam_service.delete_registration(db, registration_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration not found")
