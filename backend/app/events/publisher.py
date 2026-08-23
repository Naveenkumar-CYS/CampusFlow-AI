"""
Domain Event Publisher -- Person A's producer-side integration point.

    A's domain service -> publish() -> ProducerAdapter -> CanonicalEvent
        -> transport -> B's EventConsumer -> RuleEngine -> WorkflowEngine

This is PHASE 8/13's boundary: it is the ONLY place in Person A's code
that talks to `app.automation.*` / `app.events.*`. Every domain service
(fee, hostel, exam, attendance, ...) calls `publish()` after its own DB
commit; this module is responsible for translating that into whatever
shape B's adapter/engine wants and handing it to a transport.

Two transports, chosen via Settings.automation_transport (env var
AUTOMATION_TRANSPORT):

    "in_process" (default) -- calls EventConsumer.consume() directly, in
        the same request, same DB session. Zero moving parts. This is
        what every existing unit test exercises and keeps exercising
        unchanged -- nothing about this path changed.
    "redis" -- publishes the CanonicalEvent onto the Redis Stream
        (app.events.redis_bus.RedisStreamEventBus) and returns
        immediately with status="queued". A separate event-worker
        process (app/worker.py, running app.events.runner.EventBusRunner)
        is what actually reads it off the stream and drives it through
        EventConsumer -- see app/worker.py for that side.

This keeps the "real domain API -> DB -> event -> Redis -> processor"
architecture real for integration/prod while leaving every existing
in-process unit test (rules/workflows/actions/notifications/idempotency/
retries/AI) untouched, since none of them set AUTOMATION_TRANSPORT.

CRITICAL EVENT RULE (per the Day 3-4 brief): publish() must only ever be
called AFTER the triggering domain write has committed. Never publish
speculatively before a commit.

Not every domain event has a rule/workflow behind it yet (e.g.
student.created has no automation consumer today) -- publish() handles
that by returning None rather than raising, since "no one is listening
yet" is not a producer-side error.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.automation.adapter import ProducerAdapter, UnknownProducerEventError
from app.automation.consumer import EventConsumer
from app.automation.events import CanonicalEvent, EventType
from app.automation.rules import RuleEngine
from app.automation.store import DbExecutionStore
from app.automation.workflows import WorkflowEngine
from app.core.config import get_settings
from app.services.audit import AuditService

logger = logging.getLogger("campusflow.events.publisher")

# Lazily-constructed, process-wide RedisStreamEventBus used when
# AUTOMATION_TRANSPORT=redis. Built on first use (not at import time) so
# importing this module never requires Redis to be reachable -- e.g. the
# default "in_process" test/dev path never touches this. Reused across
# calls rather than reconnecting per publish() to avoid paying a fresh
# TCP/handshake cost on every domain write.
_redis_bus = None


def _get_redis_bus():
    global _redis_bus
    if _redis_bus is None:
        from app.events.factory import get_redis_event_bus

        _redis_bus = get_redis_event_bus()
    return _redis_bus


def _adapt_fee_paid(raw: dict[str, Any]) -> CanonicalEvent:
    return CanonicalEvent(
        event_type=EventType.FEE_PAID,
        aggregate_type="fee",
        aggregate_id=raw["aggregate_id"],
        student_id=raw["student_id"],
        data=raw["data"],
    )


def _adapt_hostel_allocated(raw: dict[str, Any]) -> CanonicalEvent:
    return CanonicalEvent(
        event_type=EventType.HOSTEL_ALLOCATED,
        aggregate_type="hostel_allocation",
        aggregate_id=raw["aggregate_id"],
        student_id=raw["student_id"],
        data=raw["data"],
    )


def _adapt_exam_registered(raw: dict[str, Any]) -> CanonicalEvent:
    return CanonicalEvent(
        event_type=EventType.EXAM_REGISTERED,
        aggregate_type="exam_registration",
        aggregate_id=raw["aggregate_id"],
        student_id=raw["student_id"],
        data=raw["data"],
    )


def _adapt_attendance_marked(raw: dict[str, Any]) -> CanonicalEvent:
    return CanonicalEvent(
        event_type=EventType.ATTENDANCE_MARKED,
        aggregate_type="attendance",
        aggregate_id=raw["aggregate_id"],
        student_id=raw["student_id"],
        data=raw["data"],
    )


# Registered mappings for producer event_type -> CanonicalEvent builder.
# Only event types B's automation.events.EventType allow-list actually
# knows about get registered here -- adding a mapping for an event type
# the engine doesn't recognize would just fail validation downstream, so
# don't add one until B's EventType enum has the matching member.
_ADAPTER = ProducerAdapter()
_ADAPTER.register("fee.paid", _adapt_fee_paid)
_ADAPTER.register("hostel.allocated", _adapt_hostel_allocated)
_ADAPTER.register("exam.registered", _adapt_exam_registered)
_ADAPTER.register("attendance.marked", _adapt_attendance_marked)


def publish(
    db: Session,
    *,
    event_type: str,
    aggregate_id: str,
    student_id: str,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    """Publish a real domain event to Person B's automation backbone.

    Returns a small dict describing the outcome (event_id, status,
    workflow_id/status if one fired) for API responses / integration-test
    reporting, or None if this event_type has no registered adapter
    mapping (not an error -- just nothing to trigger yet).

    Never raises. A failure in the automation layer must not roll back
    or fail the domain write that already committed; it's logged and
    reported back as status="automation_error" instead.
    """
    raw_event = {
        "event_type": event_type,
        "aggregate_id": aggregate_id,
        "student_id": student_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }

    try:
        canonical = _ADAPTER.adapt(raw_event)
    except UnknownProducerEventError:
        logger.info(
            "no automation adapter registered for event_type=%s; not published", event_type
        )
        return None

    if get_settings().automation_transport == "redis":
        return _publish_via_redis(canonical, event_type)
    return _publish_in_process(db, canonical, event_type)


def _publish_in_process(db: Session, canonical: CanonicalEvent, event_type: str) -> dict[str, Any]:
    """Default transport: run the automation chain synchronously, in this
    request, using this request's own DB session. Unchanged behavior."""
    try:
        store = DbExecutionStore(db)
        # Stage 6: wire the same AuditService used by the manual/dummy
        # trigger endpoints (see app/api/automation.py) into the real
        # producer path too -- otherwise a genuine domain event (e.g.
        # fee.paid from services/fee.py) would silently bypass the audit
        # trail entirely, while only the manual trigger endpoints stayed
        # traceable. AuditService.record() never raises (see
        # app/services/audit.py), so this can't turn a working publish()
        # into a failing one.
        audit = AuditService(db)
        consumer = EventConsumer(
            RuleEngine(), WorkflowEngine(store, db=db, audit_service=audit), store, audit_service=audit
        )
        result = consumer.consume(canonical)
    except Exception:  # noqa: BLE001 -- automation failures must never bubble into A's response
        logger.exception(
            "automation consume failed for event_id=%s event_type=%s",
            canonical.event_id,
            event_type,
        )
        return {"event_id": canonical.event_id, "event_type": event_type, "status": "automation_error"}

    return {
        "event_id": result.event.event_id,
        "event_type": event_type,
        "status": result.status,
        "workflow_id": result.workflow_run.workflow_id if result.workflow_run else None,
        "workflow_status": result.workflow_run.status if result.workflow_run else None,
    }


def _publish_via_redis(canonical: CanonicalEvent, event_type: str) -> dict[str, Any]:
    """Real-transport path: hand the event to Redis and return immediately.
    Processing (rule match -> workflow -> actions -> notification -> audit)
    happens asynchronously, off this request, in app/worker.py.

    Never raises, same contract as the in-process path -- a Redis outage
    must not fail the domain write that already committed. Unlike
    in-process, there is no workflow_id/status to report yet at this
    point (status="queued" instead); callers that need the outcome should
    poll GET /automation/executions/{event_id} once the worker has had a
    chance to process it."""
    try:
        bus = _get_redis_bus()
        message_id = bus.publish(canonical)
    except Exception:  # noqa: BLE001 -- see _publish_in_process's contract
        logger.exception(
            "redis publish failed for event_id=%s event_type=%s",
            canonical.event_id,
            event_type,
        )
        return {"event_id": canonical.event_id, "event_type": event_type, "status": "automation_error"}

    logger.info(
        "published event_id=%s event_type=%s to redis message_id=%s",
        canonical.event_id,
        event_type,
        message_id,
    )
    return {
        "event_id": canonical.event_id,
        "event_type": event_type,
        "status": "queued",
        "workflow_id": None,
        "workflow_status": None,
    }
