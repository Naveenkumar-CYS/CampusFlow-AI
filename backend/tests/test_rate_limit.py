"""
Tests for app.core.rate_limit (Person E, Step 1).

Deliberately does NOT reuse the full app.main FastAPI app + real
Postgres the rest of the suite depends on -- these tests only need the
rate limiter itself, so they build a tiny standalone FastAPI app with
the same dependencies wired in. That keeps them runnable even when
Postgres is unavailable.

Two groups:
  * in-memory-counter unit tests -- always run, no external services.
  * Redis-backed integration tests -- skipped automatically if Redis
    is unreachable, same convention as test_event_bus.py's
    `_redis_available()`.
"""
from __future__ import annotations

import time

import pytest
import redis as redis_lib
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core import rate_limit
from app.core.config import get_settings


def _redis_available() -> bool:
    try:
        client = redis_lib.Redis.from_url(
            get_settings().redis_url, socket_timeout=0.5, socket_connect_timeout=0.5
        )
        return bool(client.ping())
    except redis_lib.RedisError:
        return False


@pytest.fixture(autouse=True)
def _reset_memory_counters():
    """Each test starts with a clean in-memory counter store, and
    restores the module's "already logged the Redis-down warning" flag
    so tests don't depend on run order."""
    rate_limit._memory_counters.clear()
    rate_limit._redis_unavailable_logged = False
    yield
    rate_limit._memory_counters.clear()


# ---------------------------------------------------------------- in-memory


def test_memory_counter_allows_up_to_limit():
    key = f"test:{time.time_ns()}"
    for _ in range(5):
        assert rate_limit._check_memory(key, limit=5, window_seconds=60) is True


def test_memory_counter_blocks_beyond_limit():
    key = f"test:{time.time_ns()}"
    for _ in range(5):
        rate_limit._check_memory(key, limit=5, window_seconds=60)
    assert rate_limit._check_memory(key, limit=5, window_seconds=60) is False


def test_memory_counter_resets_in_new_window():
    key = f"test:{time.time_ns()}"
    # window_seconds=1 so the window rolls over almost immediately
    for _ in range(3):
        rate_limit._check_memory(key, limit=3, window_seconds=1)
    assert rate_limit._check_memory(key, limit=3, window_seconds=1) is False
    time.sleep(1.1)
    assert rate_limit._check_memory(key, limit=3, window_seconds=1) is True


def test_allow_falls_back_to_memory_when_redis_unavailable(monkeypatch):
    """_allow() must not raise and must still enforce the limit when
    Redis itself is unreachable."""

    def _raise(*_args, **_kwargs):
        raise redis_lib.exceptions.ConnectionError("simulated redis outage")

    monkeypatch.setattr(rate_limit, "_check_redis", _raise)

    key = f"test:{time.time_ns()}"
    for _ in range(4):
        assert rate_limit._allow(key, limit=4, window_seconds=60) is True
    assert rate_limit._allow(key, limit=4, window_seconds=60) is False


# ---------------------------------------------------------------- dependency behavior (standalone app)


def _build_test_app() -> FastAPI:
    app = FastAPI()

    @app.post("/login", dependencies=[Depends(rate_limit.enforce_login_rate_limit)])
    def login(payload: dict):
        return {"ok": True}

    @app.post("/webhook", dependencies=[Depends(rate_limit.enforce_webhook_rate_limit)])
    def webhook():
        return {"ok": True}

    return app


def test_login_endpoint_returns_429_after_per_account_limit(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_login_per_account_max", 3)
    monkeypatch.setattr(settings, "rate_limit_login_per_ip_max", 1000)
    monkeypatch.setattr(settings, "rate_limit_login_window_seconds", 60)
    # Force the in-memory path so this test doesn't depend on Redis being up.
    monkeypatch.setattr(
        rate_limit,
        "_check_redis",
        lambda *a, **k: (_ for _ in ()).throw(redis_lib.exceptions.ConnectionError("no redis in test")),
    )

    client = TestClient(_build_test_app())
    email = f"ratelimit-{time.time_ns()}@example.edu"

    for _ in range(3):
        resp = client.post("/login", json={"email": email, "password": "whatever"})
        assert resp.status_code == 200

    resp = client.post("/login", json={"email": email, "password": "whatever"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_login_endpoint_different_accounts_are_independent(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_login_per_account_max", 1)
    monkeypatch.setattr(settings, "rate_limit_login_per_ip_max", 1000)
    monkeypatch.setattr(settings, "rate_limit_login_window_seconds", 60)
    monkeypatch.setattr(
        rate_limit,
        "_check_redis",
        lambda *a, **k: (_ for _ in ()).throw(redis_lib.exceptions.ConnectionError("no redis in test")),
    )

    client = TestClient(_build_test_app())
    suffix = time.time_ns()

    # Each distinct account gets its own allowance -- one request each
    # should succeed even though they share the same client/IP.
    for i in range(5):
        resp = client.post(
            "/login", json={"email": f"user-{suffix}-{i}@example.edu", "password": "x"}
        )
        assert resp.status_code == 200


def test_webhook_endpoint_returns_429_after_per_ip_limit(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_webhook_per_ip_max", 2)
    monkeypatch.setattr(settings, "rate_limit_webhook_window_seconds", 60)
    monkeypatch.setattr(
        rate_limit,
        "_check_redis",
        lambda *a, **k: (_ for _ in ()).throw(redis_lib.exceptions.ConnectionError("no redis in test")),
    )

    client = TestClient(_build_test_app())

    for _ in range(2):
        resp = client.post("/webhook")
        assert resp.status_code == 200

    resp = client.post("/webhook")
    assert resp.status_code == 429


def test_rate_limiting_disabled_bypasses_checks(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_enabled", False)

    client = TestClient(_build_test_app())
    email = f"ratelimit-disabled-{time.time_ns()}@example.edu"

    for _ in range(50):
        resp = client.post("/login", json={"email": email, "password": "x"})
        assert resp.status_code == 200


# ---------------------------------------------------------------- Redis-backed (integration, optional)


@pytest.mark.skipif(not _redis_available(), reason="Redis is not reachable in this environment")
def test_check_redis_enforces_limit_against_real_redis():
    key = f"test:real-redis:{time.time_ns()}"
    for _ in range(3):
        assert rate_limit._check_redis(key, limit=3, window_seconds=60) is True
    assert rate_limit._check_redis(key, limit=3, window_seconds=60) is False
