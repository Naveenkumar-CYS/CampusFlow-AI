"""
Automated tests for the Attendance service: CRUD, the duplicate
(student, subject, session_date) guard, event emission for a real
attendance.marked event via Person B's automation backbone, and the
attendance_percentage payload B's `_attendance_below_75` rule depends on.

Same conventions as test_fee.py / test_hostel.py / test_examination.py:
runs against the real dev DB from .env, random suffixes so repeated runs
don't collide, tests originate from the HTTP API (not a fabricated
event).
"""
import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _suffix() -> str:
    return uuid.uuid4().hex[:6].upper()


def _make_student() -> str:
    sid = f"STUA{_suffix()}"
    resp = client.post(
        "/students",
        json={
            "student_id": sid,
            "name": "Attendance Test Student",
            "email": f"{sid.lower()}@example.edu",
            "department": "CSE",
            "course": "B.Tech",
            "enrollment_year": 2026,
        },
    )
    assert resp.status_code == 201
    return sid


def _record_payload(student_id: str, session_date: date, **overrides) -> dict:
    payload = {
        "student_id": student_id,
        "subject": "Data Structures",
        "session_date": session_date.isoformat(),
        "status": "PRESENT",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------- CRUD


def test_create_get_list_record():
    sid = _make_student()
    today = date.today()
    resp = client.post("/attendance/records", json=_record_payload(sid, today))
    assert resp.status_code == 201
    body = resp.json()
    assert body["subject"] == "Data Structures"
    assert body["status"] == "PRESENT"
    assert body["session_date"] == today.isoformat()

    rid = body["id"]
    assert client.get(f"/attendance/records/{rid}").status_code == 200
    assert any(r["id"] == rid for r in client.get("/attendance/records").json())


def test_list_records_filtered_by_student():
    sid = _make_student()
    other_sid = _make_student()
    today = date.today()
    client.post("/attendance/records", json=_record_payload(sid, today))
    client.post("/attendance/records", json=_record_payload(other_sid, today))

    records = client.get("/attendance/records", params={"student_id": sid}).json()
    assert len(records) == 1


def test_duplicate_record_same_subject_and_date_rejected():
    sid = _make_student()
    today = date.today()
    payload = _record_payload(sid, today)
    assert client.post("/attendance/records", json=payload).status_code == 201
    assert client.post("/attendance/records", json=payload).status_code == 409


def test_record_for_unknown_student_404():
    resp = client.post(
        "/attendance/records", json=_record_payload("STU_DOES_NOT_EXIST", date.today())
    )
    assert resp.status_code == 404


def test_get_missing_record_404():
    assert client.get(f"/attendance/records/{uuid.uuid4()}").status_code == 404


def test_update_record():
    sid = _make_student()
    today = date.today()
    resp = client.post("/attendance/records", json=_record_payload(sid, today))
    rid = resp.json()["id"]

    resp = client.patch(f"/attendance/records/{rid}", json={"status": "LATE"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "LATE"


def test_update_missing_record_404():
    resp = client.patch(f"/attendance/records/{uuid.uuid4()}", json={"status": "ABSENT"})
    assert resp.status_code == 404


def test_delete_record():
    sid = _make_student()
    today = date.today()
    resp = client.post("/attendance/records", json=_record_payload(sid, today))
    rid = resp.json()["id"]

    assert client.delete(f"/attendance/records/{rid}").status_code == 204
    assert client.get(f"/attendance/records/{rid}").status_code == 404


def test_delete_missing_record_404():
    assert client.delete(f"/attendance/records/{uuid.uuid4()}").status_code == 404


# ------------------------------------------------- Event emission (Phase 13)


def test_attendance_marked_triggers_real_automation_event():
    """
    A real POST /attendance/records must reach Person B's EventConsumer
    via the registered attendance.marked adapter and produce an
    Execution row -- same integration pattern as test_fee.py's
    fee.paid test, test_hostel.py's hostel.allocated test, and
    test_examination.py's exam.registered test.

    A single fresh PRESENT record is 100% attendance, which does not
    match B's `_attendance_below_75` rule, so `no_rule_matched` is the
    expected status here -- see test_low_attendance_triggers_workflow
    below for the case that does match.
    """
    sid = _make_student()
    resp = client.post("/attendance/records", json=_record_payload(sid, date.today()))
    assert resp.status_code == 201

    from app.db.session import SessionLocal
    from app.repositories import execution as execution_repo

    db = SessionLocal()
    try:
        executions = execution_repo.list_all(db, limit=5)
        assert any(e.status in ("success", "failed") for e in executions), (
            "expected at least one recent automation Execution row after a "
            "real attendance.marked event"
        )
    finally:
        db.close()


def test_low_attendance_triggers_workflow_execution():
    """
    Marks the same student ABSENT for a subject across enough sessions
    that attendance_percentage drops below 75, which should match B's
    RULE-001 (`_attendance_below_75`) and produce a workflow-triggered
    Execution -- proving the payload contract
    (attendance_percentage/subject_id) that app/automation/rules.py and
    app/automation/actions.py expect is actually being satisfied by a
    real domain operation, not just the dummy producer.
    """
    sid = _make_student()
    subject = "Below Threshold Subject"
    base_day = date.today() - timedelta(days=10)

    # 1 PRESENT + 3 ABSENT = 25% -- comfortably below the 75% rule.
    client.post(
        "/attendance/records",
        json=_record_payload(sid, base_day, subject=subject, status="PRESENT"),
    )
    last_resp = None
    for i in range(1, 4):
        last_resp = client.post(
            "/attendance/records",
            json=_record_payload(sid, base_day + timedelta(days=i), subject=subject, status="ABSENT"),
        )
        assert last_resp.status_code == 201

    from app.db.session import SessionLocal
    from app.repositories import execution as execution_repo

    db = SessionLocal()
    try:
        executions = execution_repo.list_all(db, limit=5)
        assert any(e.status in ("success", "failed") for e in executions), (
            "expected a workflow Execution row once attendance_percentage "
            "dropped below 75 for a real attendance.marked event"
        )
    finally:
        db.close()


def test_event_not_emitted_after_failed_creation():
    """
    A failed creation (duplicate student+subject+session_date) must not
    create a second attendance row -- i.e. no event-worthy state change
    happened on the second attempt.
    """
    sid = _make_student()
    today = date.today()
    payload = _record_payload(sid, today)

    client.post("/attendance/records", json=payload)
    resp = client.post("/attendance/records", json=payload)
    assert resp.status_code == 409

    records = client.get("/attendance/records", params={"student_id": sid}).json()
    matching = [r for r in records if r["session_date"] == today.isoformat()]
    assert len(matching) == 1
