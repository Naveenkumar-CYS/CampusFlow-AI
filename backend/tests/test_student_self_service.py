"""
Tests for the two student self-service endpoints added to close the
remaining Person-C frontend blockers:

  GET /students/me  -- resolves the authenticated STUDENT's own Student
                        record (no arbitrary student_id accepted).
  GET /fees/me       -- lists only the authenticated STUDENT's own fees.

Same conventions as test_rbac.py / test_fee.py: runs against the real
dev DB configured in .env, TestClient, random suffixes so repeated runs
don't collide with leftover data.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _suffix() -> str:
    return uuid.uuid4().hex[:6].upper()


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_user_token(role: str, password: str = "correct-horse-battery-staple") -> str:
    from app.db.session import SessionLocal
    from app.services import auth as auth_service

    email = f"selfsvc.{role}.{_suffix().lower()}@example.edu"
    db = SessionLocal()
    try:
        auth_service.register_user(db, email=email, password=password, role=role)
    finally:
        db.close()

    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _make_student(admin_token: str, *, email: str | None = None) -> str:
    sid = f"STUS{_suffix()}"
    resp = client.post(
        "/students",
        json={
            "student_id": sid,
            "name": "Self Service Test Student",
            "email": email or f"{sid.lower()}@example.edu",
            "department": "CSE",
            "course": "B.Tech",
            "enrollment_year": 2026,
        },
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 201, resp.text
    return sid


def _make_student_with_login(admin_token: str) -> tuple[str, str]:
    """Creates a Student row AND a matching User login (same email), the
    same way get_owned_student() resolves ownership. Returns
    (student_id_code, token)."""
    from app.db.session import SessionLocal
    from app.services import auth as auth_service

    email = f"selfsvc.stu.{_suffix().lower()}@example.edu"
    sid = _make_student(admin_token, email=email)

    password = "correct-horse-battery-staple"
    db = SessionLocal()
    try:
        auth_service.register_user(db, email=email, password=password, role="student")
    finally:
        db.close()
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return sid, resp.json()["access_token"]


def _make_fee(admin_token: str, sid: str, **overrides) -> dict:
    payload = {
        "fee_id": f"FEES{_suffix()}",
        "student_id": sid,
        "fee_type": "tuition",
        "amount": "1500.00",
        "due_date": "2026-12-31",
    }
    payload.update(overrides)
    resp = client.post("/fees", json=payload, headers=_auth_headers(admin_token))
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------- GET /students/me


def test_students_me_requires_token():
    resp = client.get("/students/me")
    assert resp.status_code == 401


def test_students_me_requires_student_role():
    admin_token = _make_user_token("admin")
    resp = client.get("/students/me", headers=_auth_headers(admin_token))
    assert resp.status_code == 403


def test_students_me_returns_own_record():
    admin_token = _make_user_token("admin")
    sid, token = _make_student_with_login(admin_token)

    resp = client.get("/students/me", headers=_auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["student_id"] == sid


def test_students_me_404_when_no_linked_student_record():
    # A STUDENT-role login with no matching Student row (emails differ).
    student_token = _make_user_token("student")
    resp = client.get("/students/me", headers=_auth_headers(student_token))
    assert resp.status_code == 404


def test_students_me_never_leaks_another_students_record():
    """Two different logged-in students hitting /students/me must each
    only ever get their own record back -- this is what makes /students/me
    safe (unlike a client-suppliable id, there's nothing to tamper with)."""
    admin_token = _make_user_token("admin")
    sid_a, token_a = _make_student_with_login(admin_token)
    sid_b, token_b = _make_student_with_login(admin_token)

    resp_a = client.get("/students/me", headers=_auth_headers(token_a))
    resp_b = client.get("/students/me", headers=_auth_headers(token_b))

    assert resp_a.json()["student_id"] == sid_a
    assert resp_b.json()["student_id"] == sid_b
    assert sid_a != sid_b


# --------------------------------------------------------- GET /fees/me


def test_fees_me_requires_token():
    resp = client.get("/fees/me")
    assert resp.status_code == 401


def test_fees_me_requires_student_role():
    admin_token = _make_user_token("admin")
    resp = client.get("/fees/me", headers=_auth_headers(admin_token))
    assert resp.status_code == 403


def test_fees_me_404_when_no_linked_student_record():
    student_token = _make_user_token("student")
    resp = client.get("/fees/me", headers=_auth_headers(student_token))
    assert resp.status_code == 404


def test_fees_me_returns_only_own_fees():
    admin_token = _make_user_token("admin")
    sid_a, token_a = _make_student_with_login(admin_token)
    sid_b, _token_b = _make_student_with_login(admin_token)

    fee_a = _make_fee(admin_token, sid_a)
    _fee_b = _make_fee(admin_token, sid_b)

    resp = client.get("/fees/me", headers=_auth_headers(token_a))
    assert resp.status_code == 200, resp.text
    fee_ids = {f["fee_id"] for f in resp.json()}
    assert fee_a["fee_id"] in fee_ids
    assert _fee_b["fee_id"] not in fee_ids


def test_fees_me_cannot_be_redirected_to_another_student():
    """/fees/me takes no student_id input at all -- there is nothing in
    the request a client could tamper with to see someone else's fees."""
    import inspect

    from app.api.fees import list_own_fees

    params = inspect.signature(list_own_fees).parameters
    assert "student_id" not in params
    assert "fee_id" not in params
