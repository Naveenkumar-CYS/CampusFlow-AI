import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord, AttendanceStatus


def create(
    db: Session,
    *,
    student_pk: uuid.UUID,
    subject: str,
    session_date: date,
    status: AttendanceStatus,
    marked_by: str | None,
) -> AttendanceRecord:
    record = AttendanceRecord(
        student_id=student_pk,
        subject=subject,
        session_date=session_date,
        status=status,
        marked_by=marked_by,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_by_id(db: Session, record_pk: uuid.UUID) -> AttendanceRecord | None:
    return db.get(AttendanceRecord, record_pk)


def get_by_student_subject_date(
    db: Session, student_pk: uuid.UUID, subject: str, session_date: date
) -> AttendanceRecord | None:
    return db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.student_id == student_pk,
            AttendanceRecord.subject == subject,
            AttendanceRecord.session_date == session_date,
        )
    )


def list_all(
    db: Session,
    *,
    student_pk: uuid.UUID | None = None,
    subject: str | None = None,
) -> list[AttendanceRecord]:
    stmt = select(AttendanceRecord).order_by(AttendanceRecord.session_date)
    if student_pk is not None:
        stmt = stmt.where(AttendanceRecord.student_id == student_pk)
    if subject is not None:
        stmt = stmt.where(AttendanceRecord.subject == subject)
    return list(db.scalars(stmt))


def update(db: Session, record: AttendanceRecord, changes: dict) -> AttendanceRecord:
    for field, value in changes.items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


def delete(db: Session, record: AttendanceRecord) -> None:
    db.delete(record)
    db.commit()


def count_marked_and_present(
    db: Session, student_pk: uuid.UUID, subject: str
) -> tuple[int, int]:
    """Plain aggregate counts over already-committed rows (facts only,
    no prediction) -- used by the service layer to compute the
    attendance_percentage carried on the attendance.marked event. See
    app/automation/rules.py::_attendance_below_75, which expects exactly
    this field on the event payload."""
    total = (
        db.scalar(
            select(func.count()).select_from(AttendanceRecord).where(
                AttendanceRecord.student_id == student_pk,
                AttendanceRecord.subject == subject,
            )
        )
        or 0
    )
    present = (
        db.scalar(
            select(func.count()).select_from(AttendanceRecord).where(
                AttendanceRecord.student_id == student_pk,
                AttendanceRecord.subject == subject,
                AttendanceRecord.status == AttendanceStatus.PRESENT,
            )
        )
        or 0
    )
    return total, present
