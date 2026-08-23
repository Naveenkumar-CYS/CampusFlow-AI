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
