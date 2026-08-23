"""
External payment-provider webhook: verification + processing.

Provider-neutral by design (no concrete payment provider exists in this
repo yet) -- signature verification uses a generic HMAC-SHA256-over-raw-body
scheme, the same shape most providers that sign webhooks use (e.g.
Razorpay/Stripe-style `sha256=<hex>` header). Swapping in a concrete
provider's SDK later only needs `verify_signature()` to change; nothing
else in this module is provider-specific.

Idempotency deliberately reuses what the Fee Service already has instead
of introducing a new "processed webhook events" table:

    - `Fee.payment_reference` is unique-but-nullable (see app/models/fee.py)
      and is exactly the provider's transaction id.
    - `fee_repo.get_by_payment_reference` + the PAID/CANCELLED guards in
      `fee_service.pay_fee` already prevent a fee from being paid twice.

So the only new idempotency logic this module adds is: if the webhook's
`payment_reference` matches the reference already stored on an already-PAID
fee, this is a replay of a webhook we already processed successfully --
report it as a no-op duplicate (200) instead of an error, and do NOT
re-invoke pay_fee / re-emit fee.paid. Any other attempt to pay an
already-PAID (or CANCELLED) fee still goes through the existing
`InvalidFeeStateTransitionError` guard unchanged.

Payment processing itself is NOT reimplemented here -- it calls straight
into `app.services.fee.pay_fee`'s internal transactional helper, the exact
function `/fees/{fee_id}/pay` already uses, so verify -> persist -> emit
stays the single source of truth for what "paying a fee" means.
"""
from __future__ import annotations

import hmac
import hashlib
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.fee import FeePayRequest
from app.schemas.payment import PaymentWebhookPayload
from app.services import fee as fee_service
from app.models.fee import FeeStatus

# Provider statuses that mean "money actually moved, mark the fee PAID".
# Free-string on purpose (see PaymentWebhookPayload) -- normalized
# case-insensitively so "SUCCESS", "Success", "paid" etc. all match.
_SUCCESS_STATUSES = {"success", "succeeded", "paid", "completed", "captured"}


class InvalidWebhookSignatureError(Exception):
    """Raised when the signature header is missing or does not match."""
    pass


class WebhookFeeNotFoundError(Exception):
    """Raised when the webhook references a fee_id that doesn't exist."""
    pass


class WebhookAmountMismatchError(Exception):
    """Raised when the webhook's amount doesn't match the fee's amount."""
    pass


@dataclass
class WebhookProcessingResult:
    fee: Any  # app.models.fee.Fee
    duplicate: bool
    processed: bool  # False when the webhook was a non-success status (acknowledged, not paid)
    automation: dict | None  # publisher's outcome dict, or None if no adapter was registered


def verify_signature(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    """Constant-time HMAC-SHA256 verification over the raw request body.

    Expects a header of the form ``sha256=<hexdigest>`` (the header value
    only, not the header name). Returns False -- never raises -- so callers
    decide how to turn "not verified" into an HTTP error.
    """
    if not signature_header:
        return False

    prefix = "sha256="
    candidate = signature_header.strip()
    if candidate.startswith(prefix):
        candidate = candidate[len(prefix):]

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    try:
        return hmac.compare_digest(candidate, expected)
    except (TypeError, ValueError):
        # compare_digest raises on non-hex/odd-length garbage input rather
        # than just returning False -- treat any malformed header as "not verified".
        return False


def process_webhook(db: Session, payload: PaymentWebhookPayload) -> WebhookProcessingResult:
    """Idempotency check -> find fee -> validate -> pay -> emit fee.paid.

    Never trusts the webhook blindly: the fee must exist, must be in a
    payable state (or this must be an exact replay of an already-processed
    payment), and a stated amount must match the fee's amount.
    """
    fee = fee_service.get_fee(db, payload.fee_id)
    if fee is None:
        raise WebhookFeeNotFoundError(f"fee '{payload.fee_id}' not found")

    # --- Idempotency: exact replay of a payment we already completed.
    if fee.status == FeeStatus.PAID and fee.payment_reference == payload.payment_reference:
        return WebhookProcessingResult(fee=fee, duplicate=True, processed=False, automation=None)

    # --- Non-success provider status: acknowledge, but never mark paid.
    if payload.status.strip().lower() not in _SUCCESS_STATUSES:
        return WebhookProcessingResult(fee=fee, duplicate=False, processed=False, automation=None)

    # --- Amount tampering/mismatch guard.
    if payload.amount is not None and payload.amount != fee.amount:
        raise WebhookAmountMismatchError(
            f"webhook amount {payload.amount} does not match fee amount {fee.amount}"
        )

    # Any other invalid transition (already PAID with a *different*
    # reference, or CANCELLED) is left to raise out of pay_fee unchanged --
    # same InvalidFeeStateTransitionError / DuplicatePaymentReferenceError
    # the direct /fees/{fee_id}/pay endpoint already raises.
    paid_fee, automation_result = fee_service.pay_fee_with_automation_result(
        db, payload.fee_id, FeePayRequest(payment_reference=payload.payment_reference)
    )
    return WebhookProcessingResult(
        fee=paid_fee, duplicate=False, processed=True, automation=automation_result
    )
