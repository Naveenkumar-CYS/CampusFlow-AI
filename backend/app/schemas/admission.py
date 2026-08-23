import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, ConfigDict

from app.models.admission import AdmissionStatus


class AdmissionCreate(BaseModel):
    application_number: str
    applicant_name: str
    applicant_email: EmailStr
    department: str
    course: str
    enrollment_year: int
    application_date: date
    admission_type: str = "regular"


class AdmissionUpdate(BaseModel):
    """Partial update. Status transitions go through this too (e.g. {"status": "APPROVED"})."""
    applicant_name: str | None = None
    applicant_email: EmailStr | None = None
    department: str | None = None
    course: str | None = None
    enrollment_year: int | None = None
    admission_type: str | None = None
    status: AdmissionStatus | None = None


class AdmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_number: str
    student_id: uuid.UUID | None
    applicant_name: str
    applicant_email: EmailStr
    department: str
    course: str
    enrollment_year: int
    application_date: date
    admission_type: str
    status: AdmissionStatus
    created_at: datetime
    updated_at: datetime
