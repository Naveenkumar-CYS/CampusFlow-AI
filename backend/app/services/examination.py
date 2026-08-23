from sqlalchemy.orm import Session

from app.events.publisher import publish
from app.models.examination import Exam, ExamRegistration
from app.repositories import examination as exam_repo
from app.repositories import student as student_repo
from app.schemas.examination import ExamCreate, ExamUpdate, RegistrationCreate


class DuplicateExamError(Exception):
    pass


class ExamNotFoundError(Exception):
    pass


class StudentNotFoundError(Exception):
    pass


class DuplicateRegistrationError(Exception):
    pass


# ----------------------------------------------------------------------- Exam


def create_exam(db: Session, data: ExamCreate) -> Exam:
    if exam_repo.get_exam_by_code(db, data.exam_code) is not None:
        raise DuplicateExamError(f"exam_code '{data.exam_code}' already exists")
    return exam_repo.create_exam(
        db, exam_code=data.exam_code, subject=data.subject, scheduled_at=data.scheduled_at
    )


def get_exam(db: Session, exam_code: str) -> Exam | None:
    return exam_repo.get_exam_by_code(db, exam_code)


def list_exams(db: Session) -> list[Exam]:
    return exam_repo.list_exams(db)


def update_exam(db: Session, exam_code: str, data: ExamUpdate) -> Exam | None:
    exam = exam_repo.get_exam_by_code(db, exam_code)
    if exam is None:
        return None
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return exam
    return exam_repo.update_exam(db, exam, changes)


def delete_exam(db: Session, exam_code: str) -> bool:
    exam = exam_repo.get_exam_by_code(db, exam_code)
    if exam is None:
        return False
    exam_repo.delete_exam(db, exam)  # FK RESTRICT raises IntegrityError if Registrations exist
    return True


# ---------------------------------------------------------------- Registration


def register_student(
    db: Session, exam_code: str, data: RegistrationCreate
) -> ExamRegistration:
    """
    validate -> check duplicate -> persist -> emit exam.registered.

    Mirrors the Fee/Hostel services' shape: every guard runs before any
    write, and the event is only ever published after the registration
    has actually committed.
    """
    exam = exam_repo.get_exam_by_code(db, exam_code)
    if exam is None:
        raise ExamNotFoundError(f"exam '{exam_code}' not found")

    student = student_repo.get_by_student_id(db, data.student_id)
    if student is None:
        raise StudentNotFoundError(f"student '{data.student_id}' not found")

    existing = exam_repo.get_registration_by_student_and_exam(db, student.id, exam.id)
    if existing is not None:
        raise DuplicateRegistrationError(
            f"student '{data.student_id}' is already registered for exam '{exam_code}'"
        )

    registration = exam_repo.create_registration(db, student_pk=student.id, exam_pk=exam.id)

    # Post-commit, best-effort publish to Person B's automation backbone --
    # same Critical Event Rule as fee.paid/hostel.allocated: never publish
    # before the commit, and a failure here must never look like the
    # registration failed.
    publish(
        db,
        event_type="exam.registered",
        aggregate_id=str(registration.id),
        student_id=student.student_id,
        data={
            "registration_id": str(registration.id),
            "student_id": student.student_id,
            "exam_code": exam.exam_code,
            "subject": exam.subject,
            "scheduled_at": exam.scheduled_at.isoformat(),
        },
    )

    return registration


def get_registration(db: Session, registration_id) -> ExamRegistration | None:
    return exam_repo.get_registration_by_id(db, registration_id)


def list_registrations(
    db: Session, exam_code: str, *, student_id: str | None = None
) -> list[ExamRegistration]:
    exam = exam_repo.get_exam_by_code(db, exam_code)
    if exam is None:
        raise ExamNotFoundError(f"exam '{exam_code}' not found")

    student_pk = None
    if student_id is not None:
        student = student_repo.get_by_student_id(db, student_id)
        if student is None:
            raise StudentNotFoundError(f"student '{student_id}' not found")
        student_pk = student.id

    return exam_repo.list_registrations(db, exam_pk=exam.id, student_pk=student_pk)


def delete_registration(db: Session, registration_id) -> bool:
    registration = exam_repo.get_registration_by_id(db, registration_id)
    if registration is None:
        return False
    exam_repo.delete_registration(db, registration)
    return True
