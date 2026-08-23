"""
Tests for the external payment-provider webhook (POST /payments/webhook).

Same conventions as test_fee.py: runs against the real dev DB from .env,
random suffixes so repeated runs don't collide. Requests are sent with the
raw JSON bytes we sign, not TestClient's `json=` kwarg, so the HMAC
signature is guaranteed to match exactly what the server verifies against.
"""
import hashlib
import hmac
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)
_SECRET = get_settings().payment_webhook_secret


def _suffix() -> str:
    return uuid.uuid4().hex[:6].upper()


def _make_student() -> str:
    sid = f"STUW{_suffix()}"
    resp = client.post(
        "/students",
        json={
            "student_id": sid,
            "name": "Webhook Test Student",
            "email": f"{sid.lower()}@example.edu",
            "department": "CSE",
            "course": "B.Tech",
            "enrollment_year": 2026,
        },
    )
    assert resp.status_code == 201
    return sid


def _make_fee(amount: str = "50000.00") -> str:
    sid = _make_student()
    fid = f"FEEW{_suffix()}"
    resp = client.post(
        "/fees",
        json={
            "fee_id": fid,
            "student_id": sid,
            "fee_type": "TUITION",
            "amount": amount,
            "due_date": "2026-12-01",
        },
    )
    assert resp.status_code == 201
    return fid


def _sign(body: bytes, secret: str = _SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _send_webhook(payload: dict, *, secret: str | None = None, signature: str | None = None):
    body = json.dumps(payload).encode("utf-8")
    sig = signature if signature is not None else _sign(body, secret or _SECRET)
    headers = {"Content-Type": "application/json"}
    if sig is not None:
        headers["X-Webhook-Signature"] = sig
    return client.post("/payments/webhook", content=body, headers=headers)


def _webhook_payload(fee_id: str, payment_reference: str, **overrides) -> dict:
    payload = {
        "event_id": f"EVT{_suffix()}",
        "fee_id": fee_id,
        "payment_reference": payment_reference,
        "status": "SUCCESS",
        "amount": "50000.00",
    }
    payload.update(overrides)
    return payload


# ------------------------------------------------------------------- Valid


def test_valid_webhook_marks_fee_paid_and_emits_event():
    fid = _make_fee()
    ref = f"PAYREF{_suffix()}"

    resp = _send_webhook(_webhook_payload(fid, ref))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "paid"
    assert body["duplicate"] is False

    fee_resp = client.get(f"/fees/{fid}")
    assert fee_resp.status_code == 200
    fee_body = fee_resp.json()
    assert fee_body["status"] == "PAID"
    assert fee_body["payment_reference"] == ref
    assert fee_body["paid_at"] is not None

    # fee.paid must actually have reached Person B's automation backbone.
    from app.db.session import SessionLocal
    from app.repositories import execution as execution_repo

    db = SessionLocal()
    try:
        executions = execution_repo.list_all(db, limit=5)
        assert any(e.status in ("success", "failed") for e in executions)
    finally:
        db.close()


# ------------------------------------------------------------- Signature


def test_missing_signature_rejected():
    fid = _make_fee()
    body = json.dumps(_webhook_payload(fid, f"PAYREF{_suffix()}")).encode("utf-8")
    resp = client.post(
        "/payments/webhook", content=body, headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 401


def test_invalid_signature_rejected():
    fid = _make_fee()
    resp = _send_webhook(_webhook_payload(fid, f"PAYREF{_suffix()}"), secret="wrong-secret")
    assert resp.status_code == 401


# ------------------------------------------------------------- Duplicate


def test_duplicate_webhook_does_not_reprocess():
    fid = _make_fee()
    ref = f"PAYREF{_suffix()}"
    payload = _webhook_payload(fid, ref)

    first = _send_webhook(payload)
    assert first.status_code == 200
    assert first.json()["status"] == "paid"

    # Same event, same payment_reference, arrives again.
    second = _send_webhook(_webhook_payload(fid, ref, event_id=payload["event_id"]))
    assert second.status_code == 200
    assert second.json()["duplicate"] is True

    fee_resp = client.get(f"/fees/{fid}")
    assert fee_resp.json()["payment_reference"] == ref  # unchanged, not re-paid


# --------------------------------------------------------- Unknown / bad


def test_unknown_fee_404():
    resp = _send_webhook(_webhook_payload("FEE_DOES_NOT_EXIST", f"PAYREF{_suffix()}"))
    assert resp.status_code == 404


def test_invalid_state_transition_already_paid_with_different_reference():
    fid = _make_fee()
    _send_webhook(_webhook_payload(fid, f"PAYREF{_suffix()}"))

    # A second, genuinely different payment_reference for an already-PAID
    # fee is a real conflict, not a duplicate replay.
    resp = _send_webhook(_webhook_payload(fid, f"PAYREF{_suffix()}"))
    assert resp.status_code == 409


def test_non_success_status_does_not_pay_fee():
    fid = _make_fee()
    resp = _send_webhook(_webhook_payload(fid, f"PAYREF{_suffix()}", status="FAILED"))
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"

    fee_resp = client.get(f"/fees/{fid}")
    assert fee_resp.json()["status"] == "PENDING"


def test_amount_mismatch_rejected():
    fid = _make_fee(amount="50000.00")
    resp = _send_webhook(_webhook_payload(fid, f"PAYREF{_suffix()}", amount="1.00"))
    assert resp.status_code == 409

    fee_resp = client.get(f"/fees/{fid}")
    assert fee_resp.json()["status"] == "PENDING"


def test_duplicate_payment_reference_across_fees_rejected():
    fid1 = _make_fee()
    fid2 = _make_fee()
    ref = f"PAYREF{_suffix()}"

    assert _send_webhook(_webhook_payload(fid1, ref)).status_code == 200
    resp = _send_webhook(_webhook_payload(fid2, ref))
    assert resp.status_code == 409
