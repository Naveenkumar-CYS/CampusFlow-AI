from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.rbac import Role, require_roles
from app.db.session import get_db
from app.schemas.admission import AdmissionCreate, AdmissionRead, AdmissionUpdate
from app.services import admission as admission_service

router = APIRouter(
    prefix="/admissions",
    tags=["admissions"],
    # Admission handles applicants before they have a Student/user record,
    # so this is an ADMIN-only back-office workflow — no student self-service.
    dependencies=[Depends(require_roles(Role.ADMIN))],
)


@router.post("", response_model=AdmissionRead, status_code=status.HTTP_201_CREATED)
def create_admission(payload: AdmissionCreate, db: Session = Depends(get_db)) -> AdmissionRead:
    try:
        admission = admission_service.create_admission(db, payload)
    except admission_service.DuplicateAdmissionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return admission


@router.get("/{application_number}", response_model=AdmissionRead)
def get_admission(application_number: str, db: Session = Depends(get_db)) -> AdmissionRead:
    admission = admission_service.get_admission(db, application_number)
    if admission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
    return admission


@router.get("", response_model=list[AdmissionRead])
def list_admissions(db: Session = Depends(get_db)) -> list[AdmissionRead]:
    return admission_service.list_admissions(db)


@router.patch("/{application_number}", response_model=AdmissionRead)
def update_admission(
    application_number: str, payload: AdmissionUpdate, db: Session = Depends(get_db)
) -> AdmissionRead:
    admission = admission_service.update_admission(db, application_number, payload)
    if admission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
    return admission


@router.delete("/{application_number}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admission(application_number: str, db: Session = Depends(get_db)) -> None:
    deleted = admission_service.delete_admission(db, application_number)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found")
