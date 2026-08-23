import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"
    EXCUSED = "EXCUSED"


class AttendanceRecord(Base):
    """Records the fact of a student's attendance for one subject on one
    session date. Deliberately dumb: no prediction, no aggregation logic
    lives on the model itself -- attendance_percentage (consumed by
    Person B's automation rule) is computed in the service layer from
    plain counts over these rows, never stored here."""

    __tablename__ = "attendance_records"
    __table_args__ = (
        # A student has at most one attendance record per subject per
        # session date -- re-marking the same session is a correction
        # (PATCH), not a new fact. Same "plain global uniqueness"
        # precedent as ExamRegistration.student_id+exam_id: no re-marking
        # state machine, just one row per (student, subject, date).
        UniqueConstraint(
            "student_id",
            "subject",
            "session_date",
            name="uq_attendance_records_student_subject_session_date",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # An attendance record always belongs to an existing Student --
    # RESTRICT for the same institutional-record reasoning as
    # Fee.student_id / HostelAllocation.student_id / ExamRegistration.student_id:
    # attendance history must not silently disappear or be orphaned if a
    # Student row is ever deleted.
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Plain string, not a normalized Subject/Course entity -- same
    # precedent as Exam.subject / Fee.fee_type: institution-defined and
    # free-form, doesn't earn a dedicated table yet.
    subject: Mapped[str] = mapped_column(String(120), nullable=False)

    # Date-only, not a timestamp -- unlike Exam.scheduled_at (a specific
    # moment), attendance is a per-day fact, same precedent as
    # Fee.due_date.
    session_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_status"),
        nullable=False,
        default=AttendanceStatus.PRESENT,
    )

    # Optional faculty/marker identifier -- free-text (staff id or name),
    # not a FK, since no Faculty entity exists in this codebase yet.
    marked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
