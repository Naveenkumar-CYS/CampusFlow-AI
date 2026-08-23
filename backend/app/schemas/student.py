import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, ConfigDict


class StudentCreate(BaseModel):
    student_id: str
    name: str
    email: EmailStr
    department: str
    course: str
    enrollment_year: int
    phone: str | None = None


class StudentUpdate(BaseModel):
    """All fields optional — only provided fields are changed (PATCH semantics)."""
    name: str | None = None
    email: EmailStr | None = None
    department: str | None = None
    course: str | None = None
    enrollment_year: int | None = None
    phone: str | None = None


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: str
    name: str
    email: EmailStr
    department: str
    course: str
    enrollment_year: int
    phone: str | None
    created_at: datetime
    updated_at: datetime
