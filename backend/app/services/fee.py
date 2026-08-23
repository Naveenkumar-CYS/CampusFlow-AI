from sqlalchemy.orm import Session

from app.events.publisher import publish
from app.models.fee import Fee, FeeStatus
from app.repositories import fee as fee_repo
from app.repositories import student as student_repo
from app.schemas.fee import FeeCreate, FeePayRequest, FeeUpdate


class DuplicateFeeError(Exception):
    pass


class StudentNotFoundError(Exception):
    pass


class DuplicatePaymentReferenceError(Exception):
    """Raised when a payment_reference has already been used on another fee."""
    pass


class InvalidFeeStateTransitionError(Exception):
    """Raised when trying to pay a fee that isn't in a payable state."""
    pass


def create_fee(db: Session, data: FeeCreate) -> Fee:
    if fee_repo.get_by_fee_id(db, data.fee_id) is not None:
        raise DuplicateFeeError(f"fee_id '{data.fee_id}' already exists")

    student = student_repo.get_by_student_id(db, data.student_id)
    if student is None:
        raise StudentNotFoundError(f"student '{data.student_id}' not found")

    return fee_repo.create(
        db,
        fee_id=data.fee_id,
        student_pk=student.id,
        fee_type=data.fee_type,
        amount=data.amount,
        due_date=data.due_date,
    )


def get_fee(db: Session, fee_id: str) -> Fee | None:
    return fee_repo.get_by_fee_id(db, fee_id)


def list_fees(db: Session) -> list[Fee]:
    return fee_repo.list_all(db)


def update_fee(db: Session, fee_id: str, data: FeeUpdate) -> Fee | None:
    fee = fee_repo.get_by_fee_id(db, fee_id)
    if fee is None:
        return None
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return fee
    return fee_repo.update(db, fee, changes)


def delete_fee(db: Session, fee_id: str) -> bool:
    fee = fee_repo.get_by_fee_id(db, fee_id)
    if fee is None:
        return False
    fee_repo.delete(db, fee)
    return True


def pay_fee(db: Session, fee_id: str, data: FeePayRequest) -> Fee | None:
    """
    validate -> update fee state -> persist -> emit domain event.

    Never marks a fee PAID without a valid state transition, and never
    publishes fee.paid before the state change has committed (see the
    Critical Event Rule in the Day 3-4 brief).

    Thin wrapper around pay_fee_with_automation_result() that keeps this
    function's existing return type (Fee | None) exactly as every current
    caller (the /fees/{fee_id}/pay route, existing tests) already expects.
    """
    fee, _automation_result = pay_fee_with_automation_result(db, fee_id, data)
    return fee


def pay_fee_with_automation_result(
    db: Session, fee_id: str, data: FeePayRequest
) -> tuple[Fee | None, dict | None]:
    """
    Same validate -> persist -> emit flow as pay_fee(), but also returns the
    publisher's outcome dict (or None if no adapter was registered for
    fee.paid). Added for the payment webhook, which -- unlike the direct
    /fees/{fee_id}/pay caller -- needs to know whether the fee.paid event
    actually made it into the automation backbone so it doesn't report an
    unqualified success back to the provider when that step failed. Contains
    the exact same logic pay_fee() always had; nothing about payment
    processing itself changed.
    """
    fee = fee_repo.get_by_fee_id(db, fee_id)
    if fee is None:
        return None, None

    if fee.status == FeeStatus.PAID:
        raise InvalidFeeStateTransitionError(f"fee '{fee_id}' is already PAID")
    if fee.status == FeeStatus.CANCELLED:
        raise InvalidFeeStateTransitionError(f"fee '{fee_id}' is CANCELLED and cannot be paid")

    existing = fee_repo.get_by_payment_reference(db, data.payment_reference)
    if existing is not None and existing.id != fee.id:
        raise DuplicatePaymentReferenceError(
            f"payment_reference '{data.payment_reference}' has already been used"
        )

    fee = fee_repo.mark_paid(db, fee, data.payment_reference)

    student = student_repo.get_by_id(db, fee.student_id)

    # Commit above has already happened -- this is a post-commit,
    # best-effort publish to Person B's automation backbone. A failure
    # here must never look like the payment failed; pay_fee() has
    # already succeeded and returns the paid Fee regardless.
    automation_result = publish(
        db,
        event_type="fee.paid",
        aggregate_id=fee.fee_id,
        student_id=student.student_id if student else str(fee.student_id),
        data={
            "fee_id": fee.fee_id,
            "fee_type": fee.fee_type,
            "amount": str(fee.amount),
            "payment_reference": fee.payment_reference,
            "paid_at": fee.paid_at.isoformat() if fee.paid_at else None,
        },
    )

    return fee, automation_result
