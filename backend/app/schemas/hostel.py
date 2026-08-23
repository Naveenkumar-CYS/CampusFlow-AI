import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.hostel import AllocationStatus

# --------------------------------------------------------------------- Hostel


class HostelCreate(BaseModel):
    hostel_code: str
    name: str


class HostelUpdate(BaseModel):
    """Partial update."""
    name: str | None = None


class HostelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hostel_code: str
    name: str
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------------ Room


class RoomCreate(BaseModel):
    hostel_code: str  # human-readable Hostel.hostel_code, resolved to the FK server-side
    room_number: str
    capacity: int = Field(gt=0)


class RoomUpdate(BaseModel):
    """Partial update. Does NOT allow changing current_occupancy directly --
    that only ever changes as a side effect of allocation create/vacate,
    so it can never drift from the actual set of ACTIVE allocations."""
    room_number: str | None = None
    capacity: int | None = Field(default=None, gt=0)


class RoomRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hostel_id: uuid.UUID
    room_number: str
    capacity: int
    current_occupancy: int
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------ Allocation


class AllocationCreate(BaseModel):
    student_id: str  # human-readable Student.student_id, resolved to the FK server-side
    room_id: uuid.UUID  # Room has no separate human-readable code; UUID is the reference


class AllocationUpdate(BaseModel):
    """Partial update. `status` is the only field that may change after
    creation, and only to VACATED or CANCELLED (see service layer for the
    allowed-transition rules) -- student_id/room_id never change on an
    existing allocation; create a new one instead."""
    status: AllocationStatus | None = None


class AllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    room_id: uuid.UUID
    status: AllocationStatus
    vacated_at: datetime | None
    created_at: datetime
    updated_at: datetime
