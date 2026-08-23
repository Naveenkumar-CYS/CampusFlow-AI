"""
Lightweight API rate limiting for CampusFlow AI.

Scope (Person E, Step 1): protect the two endpoints that are the classic
abuse targets for an ERP-style backend --

  * POST /auth/login       -- credential stuffing / brute force
  * POST /payments/webhook -- flooding a public, unauthenticated endpoint

This is deliberately a dependency-level check, not middleware wrapping
every route and not logic embedded in the business/service layer --
each protected router just adds `Depends(enforce_login_rate_limit)` (or
the webhook equivalent) the same way it already adds
`Depends(get_current_user)` for auth.

Backend: a fixed-window counter stored in Redis, reusing the same
REDIS_URL the event bus already depends on (see
app/events/redis_bus.py) -- no new infrastructure is introduced, and a
shared counter in Redis is what actually makes the limit hold across
more than one API-gateway process/replica.

If Redis is unreachable (e.g. local dev without `docker compose up
redis`, or the container being temporarily down), the limiter fails
OPEN to an in-memory per-process counter rather than either taking
down login/webhook entirely or silently allowing unlimited requests.
That fallback is single-instance only (no cross-replica sharing), but
that's an acceptable degradation for a hackathon-scale deployment --
the alternative (hard-depending on Redis for login to work at all)
is worse.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict

import redis
from fastapi import HTTPException, Request, status

from app.core.config import get_settings

logger = logging.getLogger("campusflow.core.rate_limit")

# Lazily constructed -- mirrors the "don't connect eagerly" convention
# used by app.events.factory.get_redis_event_bus().
_redis_client: "redis.Redis | None" = None
_redis_client_lock = threading.Lock()

# Logged once, not on every request, to avoid log-spamming when Redis is
# down for an extended period.
_redis_unavailable_logged = False

# In-memory fallback store: key -> (window_index, count). Guarded by a
# lock because sync FastAPI routes run in Starlette's threadpool, so
# concurrent requests can land on different threads.
_memory_lock = threading.Lock()
_memory_counters: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))


def _get_redis_client() -> "redis.Redis":
    global _redis_client
    if _redis_client is None:
        with _redis_client_lock:
            if _redis_client is None:
                settings = get_settings()
                # Short timeouts on purpose: this is called on the hot
                # path of every login/webhook request, and if Redis is
                # down we want to fall back to the in-memory counter
                # quickly rather than stall the request.
                _redis_client = redis.Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_timeout=0.5,
                    socket_connect_timeout=0.5,
                )
    return _redis_client


def _check_redis(key: str, limit: int, window_seconds: int) -> bool:
    """Fixed-window counter using Redis INCR/EXPIRE. Returns True if the
    request should be allowed."""
    client = _get_redis_client()
    window_index = int(time.time()) // window_seconds
    redis_key = f"ratelimit:{key}:{window_index}"

    pipe = client.pipeline()
    pipe.incr(redis_key, 1)
    pipe.expire(redis_key, window_seconds)
    count, _ = pipe.execute()
    return int(count) <= limit


def _check_memory(key: str, limit: int, window_seconds: int) -> bool:
    """In-memory fallback fixed-window counter. Only exercised when Redis
    is unreachable -- see module docstring."""
    window_index = int(time.time()) // window_seconds
    with _memory_lock:
        stored_window, count = _memory_counters[key]
        if stored_window != window_index:
            stored_window, count = window_index, 0
        count += 1
        _memory_counters[key] = (stored_window, count)
        return count <= limit


def _allow(key: str, limit: int, window_seconds: int) -> bool:
    """True if this request is within the configured limit. Tries Redis
    first, falls back to the in-memory counter on any Redis error."""
    global _redis_unavailable_logged
    try:
        return _check_redis(key, limit, window_seconds)
    except redis.RedisError as exc:
        if not _redis_unavailable_logged:
            logger.warning(
                "Rate limiter: Redis unavailable (%s) -- falling back to "
                "an in-memory per-process counter until it recovers.",
                exc,
            )
            _redis_unavailable_logged = True
        return _check_memory(key, limit, window_seconds)


def _client_ip(request: Request) -> str:
    # X-Forwarded-For is only trusted as a hint for a local reverse proxy
    # setup (e.g. docker-compose) -- there's no upstream proxy in this
    # project that strips/rewrites it, so treat it as best-effort, not
    # authoritative.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _too_many_requests(retry_after_seconds: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Please try again later.",
        headers={"Retry-After": str(retry_after_seconds)},
    )


async def enforce_login_rate_limit(request: Request) -> None:
    """Dependency for POST /auth/login.

    Two layers, both configurable via env vars (see app.core.config):

      * per-account (email) -- the actual brute-force / credential-
        stuffing defense. Deliberately the tighter of the two.
      * per-IP -- a coarser ceiling so a single address can't hammer
        many different accounts either.

    Reads the email from the request body on a best-effort basis (a
    malformed body just skips the per-account layer -- the existing
    pydantic validation on the route itself still rejects it with a
    422 right after).
    """
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    ip = _client_ip(request)
    window = settings.rate_limit_login_window_seconds

    if not _allow(f"login:ip:{ip}", settings.rate_limit_login_per_ip_max, window):
        raise _too_many_requests(window)

    email: str | None = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            candidate = body.get("email")
            if isinstance(candidate, str):
                email = candidate.strip().lower()
    except Exception:  # noqa: BLE001 - malformed body, let the route's own validation handle it
        email = None

    if email and not _allow(
        f"login:acct:{email}", settings.rate_limit_login_per_account_max, window
    ):
        raise _too_many_requests(window)


def enforce_webhook_rate_limit(request: Request) -> None:
    """Dependency for POST /payments/webhook.

    Per-IP only -- the caller here is a payment provider's servers, not
    an individual account, so there is no "account" to key on. This
    guards against the endpoint being flooded (accidentally by a
    misbehaving retry loop, or deliberately) ahead of the HMAC-signature
    check that already rejects unauthenticated callers.
    """
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    ip = _client_ip(request)
    window = settings.rate_limit_webhook_window_seconds

    if not _allow(f"webhook:ip:{ip}", settings.rate_limit_webhook_per_ip_max, window):
        raise _too_many_requests(window)
