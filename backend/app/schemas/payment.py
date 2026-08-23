"""
Request/response shapes for the external payment-provider webhook.

Provider-neutral on purpose (see app/services/payment_webhook.py) --
these fields are the common shape any HMAC-signing payment provider's
"payment succeeded/failed" webhook would send. Nothing here is
provider-specific.
"""
from decimal import Decimal

from pydantic import BaseModel, Field


class PaymentWebhookPayload(BaseModel):
    # The provider's unique identifier for this webhook delivery/event.
    # Not currently used as the idempotency key (that's payment_reference,
    # see the service module docstring) but kept for logging/traceability
    # and because provider dashboards refer to retries by this id.
    event_id: str

    # CampusFlow's own human-readable fee reference (Fee.fee_id), same
    # convention as every other fee endpoint -- lets the provider round-trip
    # whatever we sent it when the payment was initiated.
    fee_id: str

    # The provider's transaction/payment id. This is what actually gets
    # persisted onto Fee.payment_reference and is the field the existing
    # duplicate-payment guard (fee_repo.get_by_payment_reference) keys off.
    payment_reference: str

    # Provider-reported outcome. Kept as a free string rather than an enum
    # since the concrete provider isn't fixed yet; normalized/checked
    # case-insensitively in the service layer.
    status: str

    amount: Decimal | None = Field(default=None, gt=0)

    provider: str | None = None


class PaymentWebhookResult(BaseModel):
    fee_id: str
    status: str
    duplicate: bool = False
