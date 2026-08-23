from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.student import StudentCreate, StudentRead, StudentUpdate
from app.services import student as student_service

router = APIRouter(prefix="/students", tags=["students"])


@router.post("", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)) -> StudentRead:
    try:
        student = student_service.create_student(db, payload)
    except student_service.DuplicateStudentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return student


@router.get("/{student_id}", response_model=StudentRead)
def get_student(student_id: str, db: Session = Depends(get_db)) -> StudentRead:
    student = student_service.get_student(db, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student


@router.get("", response_model=list[StudentRead])
def list_students(db: Session = Depends(get_db)) -> list[StudentRead]:
    return student_service.list_students(db)


@router.patch("/{student_id}", response_model=StudentRead)
def update_student(
    student_id: str, payload: StudentUpdate, db: Session = Depends(get_db)
) -> StudentRead:
    student = student_service.update_student(db, student_id, payload)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: str, db: Session = Depends(get_db)) -> None:
    try:
        deleted = student_service.delete_student(db, student_id)
    except student_service.StudentHasAdmissionsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
