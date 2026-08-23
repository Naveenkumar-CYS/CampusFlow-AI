from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.fee import FeeCreate, FeePayRequest, FeeRead, FeeUpdate
from app.services import fee as fee_service

router = APIRouter(prefix="/fees", tags=["fees"])


@router.post("", response_model=FeeRead, status_code=status.HTTP_201_CREATED)
def create_fee(payload: FeeCreate, db: Session = Depends(get_db)) -> FeeRead:
    try:
        fee = fee_service.create_fee(db, payload)
    except fee_service.DuplicateFeeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except fee_service.StudentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return fee


@router.get("/{fee_id}", response_model=FeeRead)
def get_fee(fee_id: str, db: Session = Depends(get_db)) -> FeeRead:
    fee = fee_service.get_fee(db, fee_id)
    if fee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee not found")
    return fee


@router.get("", response_model=list[FeeRead])
def list_fees(db: Session = Depends(get_db)) -> list[FeeRead]:
    return fee_service.list_fees(db)


@router.patch("/{fee_id}", response_model=FeeRead)
def update_fee(fee_id: str, payload: FeeUpdate, db: Session = Depends(get_db)) -> FeeRead:
    fee = fee_service.update_fee(db, fee_id, payload)
    if fee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee not found")
    return fee


@router.delete("/{fee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fee(fee_id: str, db: Session = Depends(get_db)) -> None:
    deleted = fee_service.delete_fee(db, fee_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee not found")


@router.post("/{fee_id}/pay", response_model=FeeRead)
def pay_fee(fee_id: str, payload: FeePayRequest, db: Session = Depends(get_db)) -> FeeRead:
    try:
        fee = fee_service.pay_fee(db, fee_id, payload)
    except fee_service.InvalidFeeStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except fee_service.DuplicatePaymentReferenceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if fee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee not found")
    return fee
