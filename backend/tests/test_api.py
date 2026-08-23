"""
Automated tests for Student and Admission APIs, including the
Admission-approval -> Student-creation workflow and FK integrity.

Runs against the real dev database configured in .env (no test-DB
isolation in Day 2 — keep it simple). Uses random suffixes so repeated
runs don't collide with leftover data.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _suffix() -> str:
    return uuid.uuid4().hex[:6].upper()


# ---------------------------------------------------------------- Student


def test_create_get_list_student():
    sid = f"STUT{_suffix()}"
    resp = client.post(
        "/students",
        json={
            "student_id": sid,
            "name": "Test Student",
            "email": f"{sid.lower()}@example.edu",
            "department": "CSE",
            "course": "B.Tech",
            "enrollment_year": 2026,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["student_id"] == sid

    resp = client.get(f"/students/{sid}")
    assert resp.status_code == 200
    assert resp.json()["student_id"] == sid

    resp = client.get("/students")
    assert resp.status_code == 200
    assert any(s["student_id"] == sid for s in resp.json())


def test_duplicate_student_id_rejected():
    sid = f"STUT{_suffix()}"
    payload = {
        "student_id": sid,
        "name": "Dup",
        "email": f"{sid.lower()}@example.edu",
        "department": "CSE",
        "course": "B.Tech",
        "enrollment_year": 2026,
    }
    assert client.post("/students", json=payload).status_code == 201
    assert client.post("/students", json=payload).status_code == 409


def test_get_missing_student_404():
    assert client.get("/students/STU_DOES_NOT_EXIST").status_code == 404


def test_update_student():
    sid = f"STUT{_suffix()}"
    client.post(
        "/students",
        json={
            "student_id": sid,
            "name": "Before",
            "email": f"{sid.lower()}@example.edu",
            "department": "CSE",
            "course": "B.Tech",
            "enrollment_year": 2026,
        },
    )
    resp = client.patch(f"/students/{sid}", json={"department": "ECE"})
    assert resp.status_code == 200
    assert resp.json()["department"] == "ECE"


def test_update_missing_student_404():
    resp = client.patch("/students/STU_DOES_NOT_EXIST", json={"name": "X"})
    assert resp.status_code == 404


def test_delete_student():
    sid = f"STUT{_suffix()}"
    client.post(
        "/students",
        json={
            "student_id": sid,
            "name": "Deletable",
            "email": f"{sid.lower()}@example.edu",
            "department": "CSE",
            "course": "B.Tech",
            "enrollment_year": 2026,
        },
    )
    assert client.delete(f"/students/{sid}").status_code == 204
    assert client.get(f"/students/{sid}").status_code == 404


# -------------------------------------------------------------- Admission


def _admission_payload(app_no: str, **overrides) -> dict:
    payload = {
        "application_number": app_no,
        "applicant_name": "Test Applicant",
        "applicant_email": f"{app_no.lower()}@example.edu",
        "department": "CSE",
        "course": "B.Tech",
        "enrollment_year": 2026,
        "application_date": "2026-06-15",
    }
    payload.update(overrides)
    return payload


def test_create_get_list_admission():
    app_no = f"APPT{_suffix()}"
    resp = client.post("/admissions", json=_admission_payload(app_no))
    assert resp.status_code == 201
    body = resp.json()
    assert body["application_number"] == app_no
    assert body["status"] == "APPLIED"
    assert body["student_id"] is None

    assert client.get(f"/admissions/{app_no}").status_code == 200
    assert any(a["application_number"] == app_no for a in client.get("/admissions").json())


def test_duplicate_admission_rejected():
    app_no = f"APPT{_suffix()}"
    payload = _admission_payload(app_no)
    assert client.post("/admissions", json=payload).status_code == 201
    assert client.post("/admissions", json=payload).status_code == 409


def test_missing_required_field_422():
    resp = client.post("/admissions", json={"application_number": f"APPT{_suffix()}"})
    assert resp.status_code == 422


def test_invalid_status_422():
    app_no = f"APPT{_suffix()}"
    client.post("/admissions", json=_admission_payload(app_no))
    resp = client.patch(f"/admissions/{app_no}", json={"status": "NOT_REAL"})
    assert resp.status_code == 422


def test_get_missing_admission_404():
    assert client.get("/admissions/APP_DOES_NOT_EXIST").status_code == 404


def test_delete_admission():
    app_no = f"APPT{_suffix()}"
    client.post("/admissions", json=_admission_payload(app_no))
    assert client.delete(f"/admissions/{app_no}").status_code == 204
    assert client.get(f"/admissions/{app_no}").status_code == 404


# ------------------------------------------------- Relationship / workflow


def test_approval_creates_student_idempotently():
    app_no = f"APPT{_suffix()}"
    client.post("/admissions", json=_admission_payload(app_no))

    resp = client.patch(f"/admissions/{app_no}", json={"status": "APPROVED"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "APPROVED"
    assert body["student_id"] is not None
    first_student_id = body["student_id"]

    # Approving again must not create a second student or change the link.
    resp2 = client.patch(f"/admissions/{app_no}", json={"status": "APPROVED"})
    assert resp2.status_code == 200
    assert resp2.json()["student_id"] == first_student_id


def test_rejected_admission_does_not_create_student():
    app_no = f"APPT{_suffix()}"
    client.post("/admissions", json=_admission_payload(app_no))
    resp = client.patch(f"/admissions/{app_no}", json={"status": "REJECTED"})
    assert resp.status_code == 200
    assert resp.json()["student_id"] is None


def test_cannot_delete_student_with_linked_admission():
    app_no = f"APPT{_suffix()}"
    client.post("/admissions", json=_admission_payload(app_no))
    approved = client.patch(f"/admissions/{app_no}", json={"status": "APPROVED"}).json()

    # Derive student_id the same way the service does (APP -> STU).
    student_id = "STU" + app_no[3:]
    resp = client.delete(f"/students/{student_id}")
    assert resp.status_code == 409

    # Student must still exist after the blocked delete.
    assert client.get(f"/students/{student_id}").status_code == 200
