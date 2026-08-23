import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FeeStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


class Fee(Base):
    __tablename__ = "fees"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Human-readable fee reference (e.g. "FEE2026001"), same convention as
    # Student.student_id / Admission.application_number.
    fee_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)

    # A fee always belongs to an existing Student -- unlike Admission,
    # there's no "not-a-student-yet" state here, so this FK is NOT nullable.
    # ON DELETE RESTRICT for the same reason as Admission: fee history is
    # an institutional record and must not silently disappear or be
    # orphaned if a Student row is ever deleted.
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Plain string, not an enum -- fee types are institution-defined and
    # will likely grow (tuition, hostel, exam, library fine, ...) without
    # needing a migration each time. Kept simple per Day-2 precedent.
    fee_type: Mapped[str] = mapped_column(String(50), nullable=False)

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[FeeStatus] = mapped_column(
        Enum(FeeStatus, name="fee_status"), nullable=False, default=FeeStatus.PENDING
    )

    # Set only once, on successful payment. Unique-but-nullable: multiple
    # PENDING fees legitimately have no reference yet (many NULLs are
    # fine under a unique index), but no two fees may ever share the same
    # payment reference once paid -- that's the duplicate-payment guard.
    payment_reference: Mapped[str | None] = mapped_column(
        String(120), unique=True, nullable=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
