import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.student import Student
from app.schemas.student import StudentCreate


def create(db: Session, data: StudentCreate) -> Student:
    student = Student(**data.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def get_by_id(db: Session, student_pk: uuid.UUID) -> Student | None:
    return db.get(Student, student_pk)


def get_by_student_id(db: Session, student_id: str) -> Student | None:
    return db.scalar(select(Student).where(Student.student_id == student_id))


def list_all(db: Session) -> list[Student]:
    return list(db.scalars(select(Student).order_by(Student.created_at)))


def update(db: Session, student: Student, changes: dict) -> Student:
    for field, value in changes.items():
        setattr(student, field, value)
    db.commit()
    db.refresh(student)
    return student


def delete(db: Session, student: Student) -> None:
    db.delete(student)
    db.commit()
