import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AllocationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    VACATED = "VACATED"
    CANCELLED = "CANCELLED"


class Hostel(Base):
    __tablename__ = "hostels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Human-readable code (e.g. "HOSTEL-A"), same convention as
    # Student.student_id / Fee.fee_id / Admission.application_number.
    hostel_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(120), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        # Room numbers are only unique within a hostel, not globally.
        UniqueConstraint("hostel_id", "room_number", name="uq_rooms_hostel_id_room_number"),
        # Belt-and-braces against overbooking: even a bug in the service
        # layer can't push occupancy out of [0, capacity] at the DB level.
        CheckConstraint("current_occupancy >= 0", name="ck_rooms_occupancy_non_negative"),
        CheckConstraint("current_occupancy <= capacity", name="ck_rooms_occupancy_le_capacity"),
        CheckConstraint("capacity > 0", name="ck_rooms_capacity_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # A Room has no meaning without its Hostel and no history worth
    # preserving independently of it, but RESTRICT (not CASCADE) keeps the
    # same "nothing disappears silently" precedent used for Student
    # elsewhere in this codebase -- a Hostel with Rooms can't be deleted
    # out from under them.
    hostel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    room_number: Mapped[str] = mapped_column(String(20), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Denormalized counter, maintained transactionally alongside
    # HostelAllocation writes (see services/hostel.py). Kept on Room
    # rather than computed via COUNT(*) on every read/allocation-check --
    # capacity checks are on the hot path for allocation and this avoids
    # a join+aggregate for every one of them.
    current_occupancy: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class HostelAllocation(Base):
    __tablename__ = "hostel_allocations"
    __table_args__ = (
        # A student may have at most one ACTIVE allocation at a time.
        # Enforced here (not just in the service layer) so a race between
        # two concurrent allocation requests can't both succeed -- Postgres
        # partial unique index, scoped to status = 'ACTIVE' only, so a
        # student can freely accumulate VACATED/CANCELLED history rows.
        Index(
            "uq_hostel_allocations_one_active_per_student",
            "student_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # An allocation always belongs to an existing Student -- RESTRICT for
    # the same institutional-record reasoning as Fee.student_id.
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status: Mapped[AllocationStatus] = mapped_column(
        Enum(AllocationStatus, name="hostel_allocation_status"),
        nullable=False,
        default=AllocationStatus.ACTIVE,
    )

    # Set only once, when the allocation transitions out of ACTIVE (via
    # the vacate/cancel state change) -- same "set once on transition"
    # pattern as Fee.paid_at.
    vacated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
