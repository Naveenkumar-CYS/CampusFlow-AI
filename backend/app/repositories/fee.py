import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fee import Fee, FeeStatus


def create(db: Session, *, fee_id: str, student_pk: uuid.UUID, fee_type: str, amount, due_date) -> Fee:
    fee = Fee(
        fee_id=fee_id,
        student_id=student_pk,
        fee_type=fee_type,
        amount=amount,
        due_date=due_date,
    )
    db.add(fee)
    db.commit()
    db.refresh(fee)
    return fee


def get_by_id(db: Session, fee_pk: uuid.UUID) -> Fee | None:
    return db.get(Fee, fee_pk)


def get_by_fee_id(db: Session, fee_id: str) -> Fee | None:
    return db.scalar(select(Fee).where(Fee.fee_id == fee_id))


def get_by_payment_reference(db: Session, payment_reference: str) -> Fee | None:
    return db.scalar(select(Fee).where(Fee.payment_reference == payment_reference))


def list_all(db: Session) -> list[Fee]:
    return list(db.scalars(select(Fee).order_by(Fee.created_at)))


def update(db: Session, fee: Fee, changes: dict) -> Fee:
    for field, value in changes.items():
        setattr(fee, field, value)
    db.commit()
    db.refresh(fee)
    return fee


def delete(db: Session, fee: Fee) -> None:
    db.delete(fee)
    db.commit()


def mark_paid(db: Session, fee: Fee, payment_reference: str) -> Fee:
    fee.status = FeeStatus.PAID
    fee.payment_reference = payment_reference
    fee.paid_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(fee)
    return fee
