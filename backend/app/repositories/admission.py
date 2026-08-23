import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admission import Admission
from app.schemas.admission import AdmissionCreate


def create(db: Session, data: AdmissionCreate) -> Admission:
    admission = Admission(**data.model_dump())
    db.add(admission)
    db.commit()
    db.refresh(admission)
    return admission


def get_by_application_number(db: Session, application_number: str) -> Admission | None:
    return db.scalar(
        select(Admission).where(Admission.application_number == application_number)
    )


def get_by_id(db: Session, admission_pk: uuid.UUID) -> Admission | None:
    return db.get(Admission, admission_pk)


def list_all(db: Session) -> list[Admission]:
    return list(db.scalars(select(Admission).order_by(Admission.created_at)))


def update(db: Session, admission: Admission, changes: dict) -> Admission:
    for field, value in changes.items():
        setattr(admission, field, value)
    db.commit()
    db.refresh(admission)
    return admission


def delete(db: Session, admission: Admission) -> None:
    db.delete(admission)
    db.commit()


def link_student(db: Session, admission: Admission, student_pk: uuid.UUID) -> Admission:
    admission.student_id = student_pk
    db.commit()
    db.refresh(admission)
    return admission
