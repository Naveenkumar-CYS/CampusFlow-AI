from sqlalchemy.orm import Session

from app.models.admission import Admission, AdmissionStatus
from app.repositories import admission as admission_repo
from app.repositories import student as student_repo
from app.schemas.admission import AdmissionCreate, AdmissionUpdate
from app.schemas.student import StudentCreate
from app.services import student as student_service


class DuplicateAdmissionError(Exception):
    pass


class StudentNotFoundError(Exception):
    """Raised if an admission is created/updated referencing a student_id that doesn't exist."""
    pass


def _derive_student_id(application_number: str) -> str:
    """
    Day-2 simplification: derive the Student's human-readable student_id
    from the admission's application_number by swapping the "APP" prefix
    for "STU" (e.g. APP2026001 -> STU2026001). This keeps the link
    deterministic and avoids a separate ID-generation scheme for Day 2.
    Revisit if application_number formats diverge from this assumption.
    """
    if application_number.upper().startswith("APP"):
        return "STU" + application_number[3:]
    return "STU" + application_number


def create_admission(db: Session, data: AdmissionCreate) -> Admission:
    if admission_repo.get_by_application_number(db, data.application_number) is not None:
        raise DuplicateAdmissionError(
            f"application_number '{data.application_number}' already exists"
        )
    return admission_repo.create(db, data)


def get_admission(db: Session, application_number: str) -> Admission | None:
    return admission_repo.get_by_application_number(db, application_number)


def list_admissions(db: Session) -> list[Admission]:
    return admission_repo.list_all(db)


def update_admission(
    db: Session, application_number: str, data: AdmissionUpdate
) -> Admission | None:
    admission = admission_repo.get_by_application_number(db, application_number)
    if admission is None:
        return None

    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return admission

    admission = admission_repo.update(db, admission, changes)

    # Automation trigger: approval creates (or links to) a Student. This
    # is idempotent — re-approving an already-linked admission is a no-op.
    if admission.status == AdmissionStatus.APPROVED and admission.student_id is None:
        admission = _link_or_create_student(db, admission)

    return admission


def _link_or_create_student(db: Session, admission: Admission) -> Admission:
    derived_student_id = _derive_student_id(admission.application_number)

    existing = student_repo.get_by_student_id(db, derived_student_id)
    if existing is not None:
        return admission_repo.link_student(db, admission, existing.id)

    student_data = StudentCreate(
        student_id=derived_student_id,
        name=admission.applicant_name,
        email=admission.applicant_email,
        department=admission.department,
        course=admission.course,
        enrollment_year=admission.enrollment_year,
    )
    try:
        student = student_service.create_student(db, student_data)
    except student_service.DuplicateStudentError:
        # Race: another request created it between our check and now.
        student = student_repo.get_by_student_id(db, derived_student_id)

    return admission_repo.link_student(db, admission, student.id)


def delete_admission(db: Session, application_number: str) -> bool:
    admission = admission_repo.get_by_application_number(db, application_number)
    if admission is None:
        return False
    admission_repo.delete(db, admission)
    return True
