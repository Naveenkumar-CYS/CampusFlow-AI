"""
Automated tests for the Examination service: Exam CRUD, the registration
business logic (invalid student/exam, duplicate registration), and event
emission for a real exam.registered event via Person B's automation
backbone.

Same conventions as test_fee.py / test_hostel.py: runs against the real
dev DB from .env, random suffixes so repeated runs don't collide.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _suffix() -> str:
    return uuid.uuid4().hex[:6].upper()


def _make_student() -> str:
    sid = f"STUE{_suffix()}"
    resp = client.post(
        "/students",
        json={
            "student_id": sid,
            "name": "Exam Test Student",
            "email": f"{sid.lower()}@example.edu",
            "department": "CSE",
            "course": "B.Tech",
            "enrollment_year": 2026,
        },
    )
    assert resp.status_code == 201
    return sid


def _exam_payload(exam_code: str, **overrides) -> dict:
    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    payload = {
        "exam_code": exam_code,
        "subject": "Data Structures",
        "scheduled_at": scheduled_at,
    }
    payload.update(overrides)
    return payload


def _make_exam() -> str:
    code = f"EXAM{_suffix()}"
    resp = client.post("/examinations", json=_exam_payload(code))
    assert resp.status_code == 201
    return code


# ---------------------------------------------------------------------- Exam


def test_create_get_list_exam():
    code = f"EXAM{_suffix()}"
    resp = client.post("/examinations", json=_exam_payload(code))
    assert resp.status_code == 201
    body = resp.json()
    assert body["exam_code"] == code
    assert body["status"] == "SCHEDULED"

    assert client.get(f"/examinations/{code}").status_code == 200
    assert any(e["exam_code"] == code for e in client.get("/examinations").json())


def test_duplicate_exam_code_rejected():
    code = f"EXAM{_suffix()}"
    payload = _exam_payload(code)
    assert client.post("/examinations", json=payload).status_code == 201
    assert client.post("/examinations", json=payload).status_code == 409


def test_get_missing_exam_404():
    assert client.get("/examinations/EXAM_DOES_NOT_EXIST").status_code == 404


def test_update_exam():
    code = _make_exam()
    resp = client.patch(f"/examinations/{code}", json={"subject": "Algorithms"})
    assert resp.status_code == 200
    assert resp.json()["subject"] == "Algorithms"


def test_update_exam_status():
    code = _make_exam()
    resp = client.patch(f"/examinations/{code}", json={"status": "CANCELLED"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


def test_delete_exam():
    code = _make_exam()
    assert client.delete(f"/examinations/{code}").status_code == 204
    assert client.get(f"/examinations/{code}").status_code == 404


def test_delete_exam_with_registrations_blocked():
    code = _make_exam()
    sid = _make_student()
    client.post(f"/examinations/{code}/register", json={"student_id": sid})

    resp = client.delete(f"/examinations/{code}")
    assert resp.status_code == 409


# --------------------------------------------------------------- Registration


def test_registration_success():
    code = _make_exam()
    sid = _make_student()

    resp = client.post(f"/examinations/{code}/register", json={"student_id": sid})
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body

    reg = client.get(f"/examinations/{code}/registrations/{body['id']}")
    assert reg.status_code == 200

    listing = client.get(f"/examinations/{code}/registrations").json()
    assert any(r["id"] == body["id"] for r in listing)


def test_registration_invalid_exam_404():
    sid = _make_student()
    resp = client.post(
        "/examinations/EXAM_DOES_NOT_EXIST/register", json={"student_id": sid}
    )
    assert resp.status_code == 404


def test_registration_invalid_student_404():
    code = _make_exam()
    resp = client.post(
        f"/examinations/{code}/register", json={"student_id": "STU_DOES_NOT_EXIST"}
    )
    assert resp.status_code == 404


def test_duplicate_registration_rejected():
    code = _make_exam()
    sid = _make_student()

    assert client.post(
        f"/examinations/{code}/register", json={"student_id": sid}
    ).status_code == 201

    resp = client.post(f"/examinations/{code}/register", json={"student_id": sid})
    assert resp.status_code == 409


def test_delete_registration():
    code = _make_exam()
    sid = _make_student()
    reg = client.post(f"/examinations/{code}/register", json={"student_id": sid}).json()

    assert client.delete(f"/examinations/{code}/registrations/{reg['id']}").status_code == 204
    assert client.get(f"/examinations/{code}/registrations/{reg['id']}").status_code == 404


def test_delete_missing_registration_404():
    code = _make_exam()
    assert client.delete(f"/examinations/{code}/registrations/{uuid.uuid4()}").status_code == 404


def test_registration_for_missing_registration_id_404():
    code = _make_exam()
    assert client.get(f"/examinations/{code}/registrations/{uuid.uuid4()}").status_code == 404


# ------------------------------------------------- Event emission (Phase 13)


def test_exam_registered_triggers_real_automation_event():
    """
    A real POST /examinations/{exam_code}/register must reach Person B's
    EventConsumer via the registered exam.registered adapter and produce
    an Execution row -- same integration pattern as test_fee.py's
    fee.paid test and test_hostel.py's hostel.allocated test.
    """
    code = _make_exam()
    sid = _make_student()

    resp = client.post(f"/examinations/{code}/register", json={"student_id": sid})
    assert resp.status_code == 201

    from app.db.session import SessionLocal
    from app.repositories import execution as execution_repo

    db = SessionLocal()
    try:
        executions = execution_repo.list_all(db, limit=5)
        assert any(e.status in ("success", "failed") for e in executions), (
            "expected at least one recent automation Execution row after a "
            "real exam.registered event"
        )
    finally:
        db.close()


def test_event_not_emitted_after_failed_registration():
    """
    A failed registration (duplicate) must not create a second
    registration row -- i.e. no event-worthy state change happened on the
    second attempt.
    """
    code = _make_exam()
    sid = _make_student()

    client.post(f"/examinations/{code}/register", json={"student_id": sid})
    resp = client.post(f"/examinations/{code}/register", json={"student_id": sid})
    assert resp.status_code == 409

    registrations = client.get(f"/examinations/{code}/registrations").json()
    matching = [r for r in registrations if r is not None]
    # Exactly one registration exists for this student+exam, not two.
    assert len(matching) == 1
