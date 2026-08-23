"""
External payment-provider webhook endpoint.

Deliberately public (no JWT/RBAC) -- the caller is the payment provider's
servers, not a logged-in CampusFlow user. Trust instead comes from HMAC
signature verification against a shared secret (see
app/services/payment_webhook.py), same as every real provider's webhook
model (Razorpay/Stripe/etc.).

This is the "separate, not-yet-built endpoint (Phase 12)" API_CONTRACT.md
already calls out under /fees/{fee_id}/pay's known limitations -- it calls
into the same pay_fee() machinery, it does not duplicate it.
"""
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import enforce_webhook_rate_limit
from app.db.session import get_db
from app.schemas.payment import PaymentWebhookPayload, PaymentWebhookResult
from app.services import fee as fee_service
from app.services import payment_webhook as webhook_service

router = APIRouter(prefix="/payments", tags=["payments"])


async def _raw_body(request: Request) -> bytes:
    # Isolated as its own async dependency so the path function below can
    # stay a plain `def` like every other route in this project (sync DB
    # calls run in FastAPI's threadpool that way, instead of blocking the
    # event loop as they would inside an `async def` route).
    return await request.body()


@router.post(
    "/webhook",
    response_model=PaymentWebhookResult,
    dependencies=[Depends(enforce_webhook_rate_limit)],
)
def payment_webhook(
    raw_body: bytes = Depends(_raw_body),
    x_webhook_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> PaymentWebhookResult:
    settings = get_settings()

    # Signature is verified over the exact raw bytes the provider signed --
    # must check this before any pydantic parsing touches the body.
    if not webhook_service.verify_signature(
        raw_body, x_webhook_signature, settings.payment_webhook_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid webhook signature"
        )

    try:
        payload = PaymentWebhookPayload.model_validate(json.loads(raw_body))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"invalid payload: {exc}"
        ) from exc

    try:
        result = webhook_service.process_webhook(db, payload)
    except webhook_service.WebhookFeeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except webhook_service.WebhookAmountMismatchError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except fee_service.InvalidFeeStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except fee_service.DuplicatePaymentReferenceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if result.duplicate:
        return PaymentWebhookResult(fee_id=payload.fee_id, status="duplicate_ignored", duplicate=True)

    if not result.processed:
        # Valid, verified webhook, but a non-success provider status
        # (e.g. a "payment failed" callback) -- acknowledged, fee untouched.
        return PaymentWebhookResult(fee_id=payload.fee_id, status="acknowledged", duplicate=False)

    # A failed/absent automation step must never be reported back to the
    # provider as an unqualified success -- the payment itself is still
    # final (per the project's existing "automation failure never rolls
    # back or hides a completed payment" rule), so this stays a 200, but
    # the body says plainly that the downstream event didn't go through.
    if result.automation is not None and result.automation.get("status") == "automation_error":
        return PaymentWebhookResult(fee_id=payload.fee_id, status="paid_event_failed", duplicate=False)

    return PaymentWebhookResult(fee_id=payload.fee_id, status="paid", duplicate=False)
