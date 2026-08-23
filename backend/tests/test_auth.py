"""
Automated tests for JWT authentication: login, and Bearer-token
verification on the protected /auth/me endpoint.

Same conventions as test_api.py: runs against the real dev DB from
.env, random suffixes so repeated runs don't collide with leftover data.

No signup endpoint exists (out of scope for this task), so the smallest
possible fixture is used: create a user directly via the service layer,
same as other test files create rows directly via app.db.session.SessionLocal
when there's no dedicated endpoint for it.
"""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings

client = TestClient(app)
settings = get_settings()


def _suffix() -> str:
    return uuid.uuid4().hex[:6].upper()


def _make_user(password: str = "correct-horse-battery-staple") -> tuple[str, str]:
    """Creates a user directly via the service layer and returns (email, password)."""
    from app.db.session import SessionLocal
    from app.services import auth as auth_service

    email = f"authtest.{_suffix().lower()}@example.edu"
    db = SessionLocal()
    try:
        auth_service.register_user(db, email=email, password=password, role="student")
    finally:
        db.close()
    return email, password


# ---------------------------------------------------------------- Login


def test_login_succeeds_with_valid_credentials():
    email, password = _make_user()
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_login_fails_with_invalid_credentials():
    email, _ = _make_user()
    resp = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert resp.status_code == 401

    resp = client.post(
        "/auth/login", json={"email": "no-such-user@example.edu", "password": "whatever"}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------- /auth/me


def test_me_without_token_returns_401():
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_invalid_token_returns_401():
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_me_with_expired_token_returns_401():
    email, _ = _make_user()
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": str(uuid.uuid4()),
        "email": email,
        "role": "student",
        "iat": now - timedelta(minutes=120),
        "exp": now - timedelta(minutes=60),
    }
    expired_token = jwt.encode(expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


def test_me_with_valid_token_succeeds():
    email, password = _make_user()
    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == email
    assert body["role"] == "student"
    assert "user_id" in body
