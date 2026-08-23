import enum
import uuid
from datetime import datetime

from sqlalchemy import (
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


class ExamStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Human-readable code (e.g. "EXAM2026001"), same convention as
    # Student.student_id / Fee.fee_id / Hostel.hostel_code.
    exam_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)

    # Plain string, not a normalized Course/Subject entity -- subjects are
    # institution-defined and free-form, same precedent as Fee.fee_type
    # and Student.course. A separate Subject table isn't earning its keep
    # here; add one later if subjects ever need their own attributes.
    subject: Mapped[str] = mapped_column(String(120), nullable=False)

    # Single timezone-aware timestamp carries both date and time -- an
    # exam is scheduled for a specific moment, not just a day (unlike
    # Fee.due_date, which is genuinely date-only).
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[ExamStatus] = mapped_column(
        Enum(ExamStatus, name="exam_status"), nullable=False, default=ExamStatus.SCHEDULED
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ExamRegistration(Base):
    __tablename__ = "exam_registrations"
    __table_args__ = (
        # A student may register for a given exam at most once. Plain
        # (not partial) unique constraint -- unlike Hostel's "one ACTIVE
        # allocation at a time" rule, there's no re-registration state
        # machine here: a registration is either present or it's been
        # deleted (see delete_registration in the service layer), so a
        # single global uniqueness rule is sufficient.
        UniqueConstraint("student_id", "exam_id", name="uq_exam_registrations_student_id_exam_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # A registration always belongs to an existing Student and Exam --
    # RESTRICT for the same institutional-record reasoning used for
    # Fee.student_id / HostelAllocation.student_id elsewhere in this
    # codebase: registration history must not silently disappear or be
    # orphaned if a Student/Exam row is ever deleted.
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exams.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
