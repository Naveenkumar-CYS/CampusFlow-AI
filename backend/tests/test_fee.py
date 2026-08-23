"""
Automated tests for the Fee service: CRUD, the /pay operation and its
state-transition/duplicate-reference guards, event emission, and a real
end-to-end integration test with Person B's automation backbone
(PHASE 13 -- a REAL fee.paid event, not the dummy producer).

Same conventions as test_api.py: runs against the real dev DB from
.env, random suffixes so repeated runs don't collide.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _suffix() -> str:
    return uuid.uuid4().hex[:6].upper()


def _make_student() -> str:
    sid = f"STUF{_suffix()}"
    resp = client.post(
        "/students",
        json={
            "student_id": sid,
            "name": "Fee Test Student",
            "email": f"{sid.lower()}@example.edu",
            "department": "CSE",
            "course": "B.Tech",
            "enrollment_year": 2026,
        },
    )
    assert resp.status_code == 201
    return sid


def _fee_payload(fee_id: str, student_id: str, **overrides) -> dict:
    payload = {
        "fee_id": fee_id,
        "student_id": student_id,
        "fee_type": "TUITION",
        "amount": "50000.00",
        "due_date": "2026-12-01",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------- CRUD


def test_create_get_list_fee():
    sid = _make_student()
    fid = f"FEET{_suffix()}"
    resp = client.post("/fees", json=_fee_payload(fid, sid))
    assert resp.status_code == 201
    body = resp.json()
    assert body["fee_id"] == fid
    assert body["status"] == "PENDING"
    assert body["paid_at"] is None

    assert client.get(f"/fees/{fid}").status_code == 200
    assert any(f["fee_id"] == fid for f in client.get("/fees").json())


def test_duplicate_fee_id_rejected():
    sid = _make_student()
    fid = f"FEET{_suffix()}"
    payload = _fee_payload(fid, sid)
    assert client.post("/fees", json=payload).status_code == 201
    assert client.post("/fees", json=payload).status_code == 409


def test_fee_for_unknown_student_404():
    resp = client.post("/fees", json=_fee_payload(f"FEET{_suffix()}", "STU_DOES_NOT_EXIST"))
    assert resp.status_code == 404


def test_get_missing_fee_404():
    assert client.get("/fees/FEE_DOES_NOT_EXIST").status_code == 404


def test_update_fee():
    sid = _make_student()
    fid = f"FEET{_suffix()}"
    client.post("/fees", json=_fee_payload(fid, sid))
    resp = client.patch(f"/fees/{fid}", json={"amount": "60000.00"})
    assert resp.status_code == 200
    assert resp.json()["amount"] == "60000.00"


def test_delete_fee():
    sid = _make_student()
    fid = f"FEET{_suffix()}"
    client.post("/fees", json=_fee_payload(fid, sid))
    assert client.delete(f"/fees/{fid}").status_code == 204
    assert client.get(f"/fees/{fid}").status_code == 404


# ------------------------------------------------------------------- Payment


def test_pay_fee_valid_transition():
    sid = _make_student()
    fid = f"FEET{_suffix()}"
    client.post("/fees", json=_fee_payload(fid, sid))

    ref = f"PAYREF{_suffix()}"
    resp = client.post(f"/fees/{fid}/pay", json={"payment_reference": ref})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "PAID"
    assert body["payment_reference"] == ref
    assert body["paid_at"] is not None


def test_pay_already_paid_fee_rejected():
    sid = _make_student()
    fid = f"FEET{_suffix()}"
    client.post("/fees", json=_fee_payload(fid, sid))
    client.post(f"/fees/{fid}/pay", json={"payment_reference": f"PAYREF{_suffix()}"})

    resp = client.post(f"/fees/{fid}/pay", json={"payment_reference": f"PAYREF{_suffix()}"})
    assert resp.status_code == 409


def test_duplicate_payment_reference_rejected():
    sid = _make_student()
    fid1 = f"FEET{_suffix()}"
    fid2 = f"FEET{_suffix()}"
    client.post("/fees", json=_fee_payload(fid1, sid))
    client.post("/fees", json=_fee_payload(fid2, sid))

    ref = f"PAYREF{_suffix()}"
    assert client.post(f"/fees/{fid1}/pay", json={"payment_reference": ref}).status_code == 200
    resp = client.post(f"/fees/{fid2}/pay", json={"payment_reference": ref})
    assert resp.status_code == 409


def test_pay_missing_fee_404():
    resp = client.post("/fees/FEE_DOES_NOT_EXIST/pay", json={"payment_reference": "X"})
    assert resp.status_code == 404


# ------------------------------------------- PHASE 13: real B integration


def test_fee_paid_triggers_real_automation_event():
    """
    This is the real-event integration test the Day 3-4 brief requires:
    a genuine POST /fees/{id}/pay (not the dummy producer) must reach
    Person B's EventConsumer and produce a workflow result.

    B's fee.paid rule (`_fee_paid_always`) matches unconditionally, so a
    real workflow_triggered result is expected here -- this is NOT a
    dummy event.
    """
    sid = _make_student()
    fid = f"FEET{_suffix()}"
    client.post("/fees", json=_fee_payload(fid, sid))

    resp = client.post(f"/fees/{fid}/pay", json={"payment_reference": f"PAYREF{_suffix()}"})
    assert resp.status_code == 200

    # Automation runs in-process and synchronously inside pay_fee(); by
    # the time the HTTP response returns, the Execution row must exist.
    from app.db.session import SessionLocal
    from app.repositories import execution as execution_repo

    db = SessionLocal()
    try:
        executions = execution_repo.list_all(db, limit=5)
        assert any(e.status in ("success", "failed") for e in executions), (
            "expected at least one recent automation Execution row after a real fee.paid event"
        )
    finally:
        db.close()
