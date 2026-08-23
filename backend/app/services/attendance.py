import uuid

from sqlalchemy.orm import Session

from app.events.publisher import publish
from app.models.attendance import AttendanceRecord
from app.repositories import attendance as attendance_repo
from app.repositories import student as student_repo
from app.schemas.attendance import AttendanceCreate, AttendanceUpdate


class StudentNotFoundError(Exception):
    pass


class DuplicateAttendanceRecordError(Exception):
    """Raised when the student already has a record for this subject on
    this session_date -- re-marking the same session is an update
    (PATCH), not a new record."""

    pass


def _attendance_percentage(total: int, present: int) -> int:
    """Plain arithmetic over already-recorded facts -- NOT a prediction.
    100 when there are no other sessions yet (nothing to mark down for
    yet); otherwise present/total as a whole-number percentage."""
    if total <= 0:
        return 100
    return round((present / total) * 100)


def _emit_attendance_marked(db: Session, record: AttendanceRecord) -> None:
    """Post-commit, best-effort publish to Person B's automation
    backbone -- same Critical Event Rule as fee.paid/hostel.allocated/
    exam.registered: never publish before the commit, and a failure here
    must never look like the marking failed."""
    student = student_repo.get_by_id(db, record.student_id)
    student_code = student.student_id if student else str(record.student_id)

    total, present = attendance_repo.count_marked_and_present(db, record.student_id, record.subject)
    pct = _attendance_percentage(total, present)

    publish(
        db,
        event_type="attendance.marked",
        aggregate_id=str(record.id),
        student_id=student_code,
        data={
            "record_id": str(record.id),
            "student_id": student_code,
            "subject_id": record.subject,
            "session_date": record.session_date.isoformat(),
            "status": record.status.value,
            "attendance_percentage": pct,
            "marked_by": record.marked_by,
        },
    )


def create_record(db: Session, data: AttendanceCreate) -> AttendanceRecord:
    """
    validate -> check duplicate -> persist -> emit attendance.marked.

    Mirrors the Fee/Hostel/Exam services' shape: every guard runs before
    any write, and the event is only ever published after the record has
    actually committed.
    """
    student = student_repo.get_by_student_id(db, data.student_id)
    if student is None:
        raise StudentNotFoundError(f"student '{data.student_id}' not found")

    existing = attendance_repo.get_by_student_subject_date(
        db, student.id, data.subject, data.session_date
    )
    if existing is not None:
        raise DuplicateAttendanceRecordError(
            f"student '{data.student_id}' already has an attendance record for "
            f"'{data.subject}' on {data.session_date}"
        )

    record = attendance_repo.create(
        db,
        student_pk=student.id,
        subject=data.subject,
        session_date=data.session_date,
        status=data.status,
        marked_by=data.marked_by,
    )

    _emit_attendance_marked(db, record)

    return record


def get_record(db: Session, record_id: uuid.UUID) -> AttendanceRecord | None:
    return attendance_repo.get_by_id(db, record_id)


def list_records(
    db: Session, *, student_id: str | None = None, subject: str | None = None
) -> list[AttendanceRecord]:
    student_pk = None
    if student_id is not None:
        student = student_repo.get_by_student_id(db, student_id)
        if student is None:
            raise StudentNotFoundError(f"student '{student_id}' not found")
        student_pk = student.id
    return attendance_repo.list_all(db, student_pk=student_pk, subject=subject)


def update_record(
    db: Session, record_id: uuid.UUID, data: AttendanceUpdate
) -> AttendanceRecord | None:
    """
    A field change here (status correction, subject/date fix) is still a
    fact about the same session, so it re-emits attendance.marked rather
    than skipping the event -- the Critical Event Rule is "never emit on
    a failed write," not "never emit on update." Never publishes if
    there were no actual changes to persist.
    """
    record = attendance_repo.get_by_id(db, record_id)
    if record is None:
        return None

    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return record

    record = attendance_repo.update(db, record, changes)

    _emit_attendance_marked(db, record)

    return record


def delete_record(db: Session, record_id: uuid.UUID) -> bool:
    record = attendance_repo.get_by_id(db, record_id)
    if record is None:
        return False
    attendance_repo.delete(db, record)
    return True
