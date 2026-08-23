from sqlalchemy.orm import Session

from app.models.student import Student
from app.repositories import student as student_repo
from app.schemas.student import StudentCreate


class DuplicateStudentError(Exception):
    pass


def create_student(db: Session, data: StudentCreate) -> Student:
    if student_repo.get_by_student_id(db, data.student_id) is not None:
        raise DuplicateStudentError(f"student_id '{data.student_id}' already exists")
    return student_repo.create(db, data)


def get_student(db: Session, student_id: str) -> Student | None:
    return student_repo.get_by_student_id(db, student_id)


def list_students(db: Session) -> list[Student]:
    return student_repo.list_all(db)
