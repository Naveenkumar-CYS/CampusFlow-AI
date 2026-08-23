import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.examination import Exam, ExamRegistration

# ----------------------------------------------------------------------- Exam


def create_exam(db: Session, *, exam_code: str, subject: str, scheduled_at) -> Exam:
    exam = Exam(exam_code=exam_code, subject=subject, scheduled_at=scheduled_at)
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


def get_exam_by_id(db: Session, exam_pk: uuid.UUID) -> Exam | None:
    return db.get(Exam, exam_pk)


def get_exam_by_code(db: Session, exam_code: str) -> Exam | None:
    return db.scalar(select(Exam).where(Exam.exam_code == exam_code))


def list_exams(db: Session) -> list[Exam]:
    return list(db.scalars(select(Exam).order_by(Exam.scheduled_at)))


def update_exam(db: Session, exam: Exam, changes: dict) -> Exam:
    for field, value in changes.items():
        setattr(exam, field, value)
    db.commit()
    db.refresh(exam)
    return exam


def delete_exam(db: Session, exam: Exam) -> None:
    db.delete(exam)
    db.commit()


# ---------------------------------------------------------------- Registration


def create_registration(
    db: Session, *, student_pk: uuid.UUID, exam_pk: uuid.UUID
) -> ExamRegistration:
    registration = ExamRegistration(student_id=student_pk, exam_id=exam_pk)
    db.add(registration)
    db.commit()
    db.refresh(registration)
    return registration


def get_registration_by_id(db: Session, registration_pk: uuid.UUID) -> ExamRegistration | None:
    return db.get(ExamRegistration, registration_pk)


def get_registration_by_student_and_exam(
    db: Session, student_pk: uuid.UUID, exam_pk: uuid.UUID
) -> ExamRegistration | None:
    return db.scalar(
        select(ExamRegistration).where(
            ExamRegistration.student_id == student_pk,
            ExamRegistration.exam_id == exam_pk,
        )
    )


def list_registrations(
    db: Session, *, exam_pk: uuid.UUID | None = None, student_pk: uuid.UUID | None = None
) -> list[ExamRegistration]:
    stmt = select(ExamRegistration).order_by(ExamRegistration.created_at)
    if exam_pk is not None:
        stmt = stmt.where(ExamRegistration.exam_id == exam_pk)
    if student_pk is not None:
        stmt = stmt.where(ExamRegistration.student_id == student_pk)
    return list(db.scalars(stmt))


def delete_registration(db: Session, registration: ExamRegistration) -> None:
    db.delete(registration)
    db.commit()
