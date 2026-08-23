import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.attendance import AttendanceStatus


class AttendanceCreate(BaseModel):
    student_id: str  # human-readable Student.student_id, resolved to the FK server-side
    subject: str
    session_date: date
    status: AttendanceStatus = AttendanceStatus.PRESENT
    marked_by: str | None = None


class AttendanceUpdate(BaseModel):
    """Partial update. Unlike FeeUpdate (which locks status behind a
    dedicated /pay transition), attendance has no state machine -- any
    field is a correction to the same recorded fact (wrong subject/date
    entered, status corrected), so all fields are editable here."""

    subject: str | None = None
    session_date: date | None = None
    status: AttendanceStatus | None = None
    marked_by: str | None = None


class AttendanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    subject: str
    session_date: date
    status: AttendanceStatus
    marked_by: str | None
    created_at: datetime
    updated_at: datetime
