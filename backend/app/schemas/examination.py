import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.examination import ExamStatus

# ----------------------------------------------------------------------- Exam


class ExamCreate(BaseModel):
    exam_code: str
    subject: str
    scheduled_at: datetime


class ExamUpdate(BaseModel):
    """Partial update."""
    subject: str | None = None
    scheduled_at: datetime | None = None
    status: ExamStatus | None = None


class ExamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exam_code: str
    subject: str
    scheduled_at: datetime
    status: ExamStatus
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------- Registration


class RegistrationCreate(BaseModel):
    student_id: str  # human-readable Student.student_id, resolved to the FK server-side


class RegistrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    exam_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
