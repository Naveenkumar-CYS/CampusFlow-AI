import uuid
from datetime import datetime

from sqlalchemy import Integer, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Student(Base):
    __tablename__ = "students"

    # Internal, stable identifier. This is what other services (fees,
    # hostel, exams) and events reference — it never changes even if the
    # human-readable enrollment number scheme changes later.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Human-readable enrollment/roll number (e.g. "STU2026001"). Unique but
    # kept separate from the primary key so re-issuing/correcting it never
    # requires touching foreign keys elsewhere.
    student_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    department: Mapped[str] = mapped_column(String(120), nullable=False)
    course: Mapped[str] = mapped_column(String(120), nullable=False)
    enrollment_year: Mapped[int] = mapped_column(Integer, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
