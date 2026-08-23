import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdmissionStatus(str, enum.Enum):
    APPLIED = "APPLIED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class Admission(Base):
    __tablename__ = "admissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Human-readable application reference (e.g. "APP2026001"), shown to
    # applicants before they're ever a Student.
    application_number: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )

    # Nullable: an admission has no linked Student until it's APPROVED and
    # the Student record is created. Set once, then never changes.
    # ON DELETE RESTRICT: a Student with admission history can't be deleted
    # out from under that history — see README for the reasoning.
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # Applicant-supplied data, captured at application time. This is
    # intentionally separate from the Student table — an applicant is not
    # a Student yet, and this data may differ from what ends up on the
    # Student record after review (e.g. course changes on approval).
    applicant_name: Mapped[str] = mapped_column(String(120), nullable=False)
    applicant_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(120), nullable=False)
    course: Mapped[str] = mapped_column(String(120), nullable=False)
    enrollment_year: Mapped[int] = mapped_column(nullable=False)

    application_date: Mapped[date] = mapped_column(Date, nullable=False)
    admission_type: Mapped[str] = mapped_column(String(50), nullable=False, default="regular")
    status: Mapped[AdmissionStatus] = mapped_column(
        Enum(AdmissionStatus, name="admission_status"),
        nullable=False,
        default=AdmissionStatus.APPLIED,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
