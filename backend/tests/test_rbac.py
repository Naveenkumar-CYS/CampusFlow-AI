"""
Security tests for the RBAC + API-gateway layer added on top of the
existing JWT authentication.

Scope: only the access-control behaviour introduced in this session
(role checks, 401/403s, and the student-can't-read-another-student
object-level rule). Domain business logic (fee math, hostel capacity,
etc.) is already covered by test_fee.py / test_hostel.py / etc. and is
intentionally not re-tested here.

Same conventions as the rest of the suite: runs against the real dev DB
configured in .env, TestClient, random suffixes so repeated runs don't
collide with leftover data.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _suffix() -> str:
    return uuid.uuid4().hex[:6].upper()


def _make_user_token(role: str, password: str = "correct-horse-battery-staple") -> str:
    """Creates a user with the given role directly via the service layer
    (no signup endpoint exists) and returns a valid access token for it."""
    from app.db.session import SessionLocal
    from app.services import auth as auth_service

    email = f"rbactest.{role}.{_suffix().lower()}@example.edu"
    db = SessionLocal()
    try:
        auth_service.register_user(db, email=email, password=password, role=role)
    finally:
        db.close()

    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_student(admin_token: str, *, email: str | None = None) -> str:
    """Creates a Student row (as ADMIN, the only role allowed to) and
    returns its human-readable student_id code."""
    sid = f"STUR{_suffix()}"
    resp = client.post(
        "/students",
        json={
            "student_id": sid,
            "name": "RBAC Test Student",
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
    """Creates a Student row AND a matching User login (same email) so
    the student can act as themselves. Returns (student_id_code, token).

    The email is shared on purpose: object-level authorization resolves
    "which Student row does this logged-in user own" by matching
    User.email to Student.email (see app.core.rbac.get_owned_student).
    """
    from app.db.session import SessionLocal
    from app.services import auth as auth_service

    email = f"stu.{_suffix().lower()}@example.edu"
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


# --------------------------------------------------------- 1/2. 401s (no / bad token)


def test_protected_endpoint_without_token_returns_401():
    resp = client.get("/students")
    assert resp.status_code == 401


def test_protected_endpoint_with_invalid_token_returns_401():
    resp = client.get("/students", headers=_auth_headers("not-a-real-token"))
    assert resp.status_code == 401


# --------------------------------------------------------- 3. correct role -> success


def test_admin_can_create_student():
    admin_token = _make_user_token("admin")
    sid = _make_student(admin_token)
    resp = client.get(f"/students/{sid}", headers=_auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["student_id"] == sid


# --------------------------------------------------------- 4. incorrect role -> 403


def test_student_cannot_create_student():
    student_token = _make_user_token("student")
    resp = client.post(
        "/students",
        json={
            "student_id": f"STUR{_suffix()}",
            "name": "Nope",
            "email": f"nope{_suffix().lower()}@example.edu",
            "department": "CSE",
            "course": "B.Tech",
            "enrollment_year": 2026,
        },
        headers=_auth_headers(student_token),
    )
    assert resp.status_code == 403


def test_faculty_cannot_delete_fee():
    admin_token = _make_user_token("admin")
    faculty_token = _make_user_token("faculty")
    sid = _make_student(admin_token)
    fee_resp = client.post(
        "/fees",
        json={
            "fee_id": f"FEER{_suffix()}",
            "student_id": sid,
            "fee_type": "tuition",
            "amount": "1000.00",
            "due_date": "2026-12-31",
        },
        headers=_auth_headers(admin_token),
    )
    assert fee_resp.status_code == 201, fee_resp.text
    fee_id = fee_resp.json()["fee_id"]

    resp = client.delete(f"/fees/{fee_id}", headers=_auth_headers(faculty_token))
    assert resp.status_code == 403


# --------------------------------------------------------- 5. object-level (IDOR)


def test_student_cannot_read_another_students_record():
    admin_token = _make_user_token("admin")
    _sid_a, token_a = _make_student_with_login(admin_token)
    sid_b, _token_b = _make_student_with_login(admin_token)

    resp = client.get(f"/students/{sid_b}", headers=_auth_headers(token_a))
    assert resp.status_code == 403


def test_student_can_read_own_record():
    admin_token = _make_user_token("admin")
    sid_a, token_a = _make_student_with_login(admin_token)

    resp = client.get(f"/students/{sid_a}", headers=_auth_headers(token_a))
    assert resp.status_code == 200
    assert resp.json()["student_id"] == sid_a


def test_student_cannot_read_another_students_fee():
    admin_token = _make_user_token("admin")
    _sid_a, token_a = _make_student_with_login(admin_token)
    sid_b, _token_b = _make_student_with_login(admin_token)

    fee_resp = client.post(
        "/fees",
        json={
            "fee_id": f"FEER{_suffix()}",
            "student_id": sid_b,
            "fee_type": "tuition",
            "amount": "500.00",
            "due_date": "2026-12-31",
        },
        headers=_auth_headers(admin_token),
    )
    assert fee_resp.status_code == 201, fee_resp.text
    fee_id = fee_resp.json()["fee_id"]

    resp = client.get(f"/fees/{fee_id}", headers=_auth_headers(token_a))
    assert resp.status_code == 403


# --------------------------------------------------------- 6. public endpoints stay public


def test_health_remains_public():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_login_remains_public():
    admin_token = _make_user_token("admin")  # just to prove login itself needs no token
    assert admin_token
