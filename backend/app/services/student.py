from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.student import Student
from app.repositories import student as student_repo
from app.schemas.student import StudentCreate, StudentUpdate


class DuplicateStudentError(Exception):
    pass


class StudentHasAdmissionsError(Exception):
    """Raised when deleting a Student that still has linked Admission records."""
    pass


def create_student(db: Session, data: StudentCreate) -> Student:
    if student_repo.get_by_student_id(db, data.student_id) is not None:
        raise DuplicateStudentError(f"student_id '{data.student_id}' already exists")
    return student_repo.create(db, data)


def get_student(db: Session, student_id: str) -> Student | None:
    return student_repo.get_by_student_id(db, student_id)


def list_students(db: Session) -> list[Student]:
    return student_repo.list_all(db)


def update_student(db: Session, student_id: str, data: StudentUpdate) -> Student | None:
    student = student_repo.get_by_student_id(db, student_id)
    if student is None:
        return None
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return student
    return student_repo.update(db, student, changes)


def delete_student(db: Session, student_id: str) -> bool:
    student = student_repo.get_by_student_id(db, student_id)
    if student is None:
        return False
    try:
        student_repo.delete(db, student)
    except IntegrityError as exc:
        db.rollback()
        raise StudentHasAdmissionsError(
            f"student '{student_id}' has linked admission records and cannot be deleted"
        ) from exc
    return True
