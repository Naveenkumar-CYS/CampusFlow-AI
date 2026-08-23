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
from app.schemas.attendance import AttendanceCreate, AttendanceRead, AttendanceUpdate
from app.services import attendance as attendance_service

router = APIRouter(prefix="/attendance", tags=["attendance"])

_STAFF = {Role.ADMIN, Role.FACULTY}


@router.post(
    "/records",
    response_model=AttendanceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*_STAFF))],
)
def create_record(payload: AttendanceCreate, db: Session = Depends(get_db)) -> AttendanceRead:
    try:
        return attendance_service.create_record(db, payload)
    except attendance_service.StudentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except attendance_service.DuplicateAttendanceRecordError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/records", response_model=list[AttendanceRead])
def list_records(
    student_id: str | None = None,
    subject: str | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_STAFF, Role.STUDENT)),
) -> list[AttendanceRead]:
    # Object-level check: a STUDENT must filter to (and only to) their own
    # student_id; staff may list freely.
    enforce_own_student_filter(
        current_user, db, staff_roles=_STAFF, requested_student_code=student_id
    )
    try:
        return attendance_service.list_records(db, student_id=student_id, subject=subject)
    except attendance_service.StudentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/records/{record_id}", response_model=AttendanceRead)
def get_record(
    record_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_STAFF, Role.STUDENT)),
) -> AttendanceRead:
    record = attendance_service.get_record(db, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")
    enforce_own_student_record(
        current_user, db, staff_roles=_STAFF, target_student_pk=record.student_id
    )
    return record


@router.patch(
    "/records/{record_id}",
    response_model=AttendanceRead,
    dependencies=[Depends(require_roles(*_STAFF))],
)
def update_record(
    record_id: uuid.UUID, payload: AttendanceUpdate, db: Session = Depends(get_db)
) -> AttendanceRead:
    try:
        record = attendance_service.update_record(db, record_id, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another attendance record already exists for that student/subject/session_date",
        ) from exc
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")
    return record


@router.delete(
    "/records/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(*_STAFF))],
)
def delete_record(record_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    deleted = attendance_service.delete_record(db, record_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")
