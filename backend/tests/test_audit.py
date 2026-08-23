"""
Stage 6 -- Audit / Traceability tests.

Mirrors the rest of the suite's DB-free style where possible (see
test_automation.py's module docstring): the integration hooks in
EventConsumer/WorkflowEngine are exercised against InMemoryExecutionStore
and a small in-process FakeAuditService recorder, so the audit *wiring*
is proven end-to-end without a running Postgres instance.

AuditService itself (sanitization, enum handling, failure isolation) is
tested directly by monkeypatching app.repositories.audit so it never
touches a real database either.

A small number of tests need a real Postgres (AuditRecord model
round-tripping through an actual session, the read-only audit API). Those
are marked @requires_db and skipped automatically -- same pattern as
test_event_bus.py's @requires_redis -- if Postgres isn't reachable.
"""
from __future__ import annotations

import uuid

import pytest

from app.automation.actions import ActionExecutor
from app.automation.consumer import EventConsumer
from app.automation.producer import make_attendance_marked_event, make_fee_paid_event
from app.automation.rules import RuleEngine
from app.automation.store import InMemoryExecutionStore
from app.automation.workflows import WorkflowEngine
from app.schemas.audit import AuditStatus, AuditType
from app.services import audit as audit_service_module
from app.services.audit import AuditService, _sanitize


# --------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------


class FakeAuditService:
    """Records every record() call verbatim (as kwargs) instead of
    touching a database. Used to assert *which* audit calls the
    automation integration hooks make, and with what identifiers --
    the wiring itself, not AuditService's own persistence logic."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def record(self, **kwargs) -> None:
        self.calls.append(kwargs)
        return None

    def by_type(self, audit_type: AuditType) -> list[dict]:
        return [c for c in self.calls if c["audit_type"] == audit_type]


class _FailingSession:
    """Stands in for a SQLAlchemy Session whose database is unreachable.
    add()/refresh() are no-ops (never reached before commit() blows up,
    but kept harmless just in case); commit() always raises."""

    def add(self, obj):
        pass

    def commit(self):
        raise RuntimeError("simulated audit database outage")

    def refresh(self, obj):
        pass

    def rollback(self):
        pass


def _consumer_with_audit(audit=None):
    store = InMemoryExecutionStore()
    rule_engine = RuleEngine()
    workflow_engine = WorkflowEngine(store, audit_service=audit)
    consumer = EventConsumer(rule_engine, workflow_engine, store, audit_service=audit)
    return consumer, store


# ======================================================================
# Error sanitization (Part 10, Part 16)
# ======================================================================


@pytest.mark.parametrize(
    "raw,should_not_contain",
    [
        ("auth failed: password=hunter2isbad", "hunter2isbad"),
        ('login error {"api_key": "sk-abcdef123456"}', "sk-abcdef123456"),
        ("request rejected, token=eyJhbGciOiJIUzI1NiIsInR5cCI6", "eyJhbGciOiJIUzI1NiIsInR5cCI6"),
        ("SMTP_PASSWORD=supersecret123 rejected by server", "supersecret123"),
        ("Authorization: Bearer abcd.efgh.ijkl", "abcd.efgh.ijkl"),
    ],
)
def test_sanitize_redacts_credential_shaped_substrings(raw, should_not_contain):
    sanitized = _sanitize(raw)
    assert sanitized is not None
    assert should_not_contain not in sanitized
    assert "[REDACTED]" in sanitized


def test_sanitize_leaves_ordinary_error_text_alone():
    message = "email provider failed: connection timed out after 3 attempts"
    assert _sanitize(message) == message


def test_sanitize_truncates_very_long_messages():
    huge = "x" * 5000
    sanitized = _sanitize(huge)
    assert len(sanitized) < len(huge)
    assert sanitized.endswith("...[truncated]")


def test_sanitize_none_is_none():
    assert _sanitize(None) is None


def test_audit_service_record_sanitizes_before_reaching_repository(monkeypatch):
    """Full AuditService.record() path (not just the regex helper) --
    proves a secret never reaches app.repositories.audit.create."""
    captured = {}

    def fake_create(db, **fields):
        captured.update(fields)
        return object()

    monkeypatch.setattr(audit_service_module.audit_repo, "create", fake_create)

    service = AuditService(db=object())
    service.record(
        audit_type=AuditType.NOTIFICATION_EXECUTED,
        status=AuditStatus.FAILED,
        component="notification_service",
        event_id="evt-1",
        error_type="provider_error",
        error_message="SMTP auth rejected: smtp_password=letmein123",
    )

    assert "letmein123" not in captured["error_message"]
    assert "[REDACTED]" in captured["error_message"]
    # enums are stored as their plain string value, not the Enum repr
    assert captured["audit_type"] == "NOTIFICATION_EXECUTED"
    assert captured["status"] == "FAILED"


# ======================================================================
# AuditService failure isolation (Part 13)
# ======================================================================


def test_audit_service_record_never_raises_on_db_failure():
    service = AuditService(db=_FailingSession())

    result = service.record(
        audit_type=AuditType.EVENT_PROCESSED,
        status=AuditStatus.SUCCESS,
        component="event_consumer",
        event_id="evt-x",
    )

    assert result is None  # failed write is reported as None, not an exception


def test_automation_chain_completes_when_audit_storage_is_down():
    """The core Part 13 guarantee: a totally broken audit backend must
    not stop the deterministic automation pipeline from running to
    completion."""
    failing_audit = AuditService(db=_FailingSession())
    consumer, _ = _consumer_with_audit(audit=failing_audit)
    event = make_attendance_marked_event(attendance_percentage=50)

    result = consumer.consume(event)

    assert result.status == "workflow_triggered"
    assert result.workflow_run.status == "success"
    assert all(a.status == "success" for a in result.workflow_run.action_results)


# ======================================================================
# Integration: EventConsumer / WorkflowEngine -> AuditService hooks
# (Part 11, Part 12)
# ======================================================================


def test_full_chain_records_expected_audit_lifecycle_for_attendance_event():
    audit = FakeAuditService()
    consumer, _ = _consumer_with_audit(audit=audit)
    event = make_attendance_marked_event(attendance_percentage=60)

    result = consumer.consume(event)

    assert result.status == "workflow_triggered"

    types_in_order = [c["audit_type"] for c in audit.calls]
    assert types_in_order[0] == AuditType.EVENT_PROCESSED
    assert AuditType.RULE_EVALUATED in types_in_order
    # attendance.marked is in-scope for the AI Advisory Service
    assert AuditType.AI_ADVISORY in types_in_order
    assert types_in_order.count(AuditType.ACTION_EXECUTED) == 2  # create_notification, record_execution
    assert types_in_order.count(AuditType.NOTIFICATION_EXECUTED) == 2  # send_email, send_sms
    assert types_in_order[-1] == AuditType.WORKFLOW_EXECUTED

    # every audited record carries the event_id -- the identifier an
    # auditor traces the whole execution by (Part 2)
    assert all(c.get("event_id") == event.event_id for c in audit.calls)

    workflow_call = audit.by_type(AuditType.WORKFLOW_EXECUTED)[0]
    assert workflow_call["status"] == AuditStatus.SUCCESS
    assert workflow_call["workflow_id"] == "attendance_warning"


def test_fee_paid_event_does_not_record_ai_advisory():
    audit = FakeAuditService()
    consumer, _ = _consumer_with_audit(audit=audit)
    event = make_fee_paid_event(amount=1000.0)

    result = consumer.consume(event)

    assert result.status == "workflow_triggered"
    assert audit.by_type(AuditType.AI_ADVISORY) == []


def test_ai_advisory_audit_carries_expected_metadata_shape():
    audit = FakeAuditService()
    consumer, _ = _consumer_with_audit(audit=audit)
    event = make_attendance_marked_event(attendance_percentage=40)

    consumer.consume(event)

    advisory_calls = audit.by_type(AuditType.AI_ADVISORY)
    assert len(advisory_calls) == 1
    call = advisory_calls[0]
    assert call["status"] in (AuditStatus.SUCCESS, AuditStatus.FAILED)
    ctx = call["context"]
    # Part 15: exactly this shape, nothing more (no raw model, no PII)
    assert set(ctx.keys()) == {"model_version", "risk_level", "risk_score", "attendance_pattern"}
    assert "student_id" not in str(call)  # no raw student identifier anywhere in the record


def test_no_rule_matched_records_event_processed_and_skipped_rule_only():
    audit = FakeAuditService()
    consumer, _ = _consumer_with_audit(audit=audit)
    event = make_attendance_marked_event(attendance_percentage=95)  # above threshold

    result = consumer.consume(event)

    assert result.status == "no_rule_matched"
    types_in_order = [c["audit_type"] for c in audit.calls]
    assert types_in_order == [AuditType.EVENT_PROCESSED, AuditType.RULE_EVALUATED]
    assert audit.calls[1]["status"] == AuditStatus.SKIPPED
    assert AuditType.WORKFLOW_EXECUTED not in types_in_order


def test_duplicate_event_records_event_processed_and_skipped_duplicate_rule():
    audit = FakeAuditService()
    consumer, _ = _consumer_with_audit(audit=audit)
    event = make_attendance_marked_event(aggregate_id="ATT-DUP-AUDIT", attendance_percentage=50)

    consumer.consume(event)
    audit.calls.clear()
    second = consumer.consume(event)

    assert second.status == "skipped_duplicate"
    types_in_order = [c["audit_type"] for c in audit.calls]
    assert types_in_order == [AuditType.EVENT_PROCESSED, AuditType.RULE_EVALUATED]
    assert audit.calls[1]["context"] == {"reason": "duplicate_event"}


def test_failed_action_records_failed_action_audit_and_stops_chain():
    audit = FakeAuditService()
    store = InMemoryExecutionStore()

    def always_fails(event, context):
        raise RuntimeError("boom: provider unreachable")

    executor = ActionExecutor(max_attempts=1, registry={"create_notification": always_fails})
    engine = WorkflowEngine(store, action_executor=executor, audit_service=audit)
    event = make_attendance_marked_event()

    run = engine.run("attendance_warning", event)

    assert run.status == "failed"
    action_calls = audit.by_type(AuditType.ACTION_EXECUTED)
    assert len(action_calls) == 1  # only the failing first step was ever attempted
    assert action_calls[0]["status"] == AuditStatus.FAILED
    assert action_calls[0]["action"] == "create_notification"
    assert "boom" in action_calls[0]["error_message"]

    workflow_call = audit.by_type(AuditType.WORKFLOW_EXECUTED)[0]
    assert workflow_call["status"] == AuditStatus.FAILED

    # a failure downstream of the AuditService's own record() call must
    # never happen here since FakeAuditService.record() cannot raise --
    # this test is about the *content* of what gets audited on failure,
    # not failure isolation (see test_automation_chain_completes_when_audit_storage_is_down
    # for that).


def test_no_audit_service_is_a_true_no_op():
    """Existing callers that never pass audit_service (e.g. every test in
    test_automation.py) must be completely unaffected -- this is the
    backward-compatibility guarantee behind Part 12's 'minimal changes'."""
    consumer, _ = _consumer_with_audit(audit=None)
    event = make_attendance_marked_event(attendance_percentage=50)

    result = consumer.consume(event)

    assert result.status == "workflow_triggered"
    assert result.workflow_run.status == "success"


# ======================================================================
# AuditService query surface (Part 6) -- repository monkeypatched so no
# real DB is required to prove AuditService delegates correctly.
# ======================================================================


def test_audit_service_get_by_event_delegates_with_event_id_filter(monkeypatch):
    captured = {}

    def fake_query(db, **filters):
        captured.update(filters)
        return ["record-a", "record-b"]

    monkeypatch.setattr(audit_service_module.audit_repo, "query", fake_query)

    service = AuditService(db=object())
    result = service.get_by_event("evt-123")

    assert result == ["record-a", "record-b"]
    assert captured["event_id"] == "evt-123"


def test_audit_service_get_by_workflow_delegates_with_workflow_id_filter(monkeypatch):
    captured = {}

    def fake_query(db, **filters):
        captured.update(filters)
        return []

    monkeypatch.setattr(audit_service_module.audit_repo, "query", fake_query)

    service = AuditService(db=object())
    service.get_by_workflow("attendance_warning")

    assert captured["workflow_id"] == "attendance_warning"


def test_audit_service_query_passes_all_filters_through(monkeypatch):
    captured = {}

    def fake_query(db, **filters):
        captured.update(filters)
        return []

    monkeypatch.setattr(audit_service_module.audit_repo, "query", fake_query)

    service = AuditService(db=object())
    service.query(
        event_id="evt-1",
        workflow_id="attendance_warning",
        status="FAILED",
        event_type="attendance.marked",
        audit_type="ACTION_EXECUTED",
        limit=10,
    )

    assert captured["event_id"] == "evt-1"
    assert captured["workflow_id"] == "attendance_warning"
    assert captured["status"] == "FAILED"
    assert captured["event_type"] == "attendance.marked"
    assert captured["audit_type"] == "ACTION_EXECUTED"
    assert captured["limit"] == 10


def test_audit_service_get_by_id_delegates(monkeypatch):
    sentinel_id = uuid.uuid4()
    captured = {}

    def fake_get_by_id(db, audit_id):
        captured["audit_id"] = audit_id
        return "the-record"

    monkeypatch.setattr(audit_service_module.audit_repo, "get_by_id", fake_get_by_id)

    service = AuditService(db=object())
    result = service.get_by_id(sentinel_id)

    assert result == "the-record"
    assert captured["audit_id"] == sentinel_id


# ======================================================================
# Real-database tests (skipped automatically if Postgres isn't reachable)
# ======================================================================


def _db_available() -> bool:
    try:
        from sqlalchemy import text

        from app.db.session import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_available(), reason="Postgres is not reachable; skipping DB-backed audit tests"
)


@requires_db
def test_audit_record_round_trips_through_real_db():
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        service = AuditService(db)
        event_id = f"evt-audit-test-{uuid.uuid4().hex[:8]}"
        created = service.record(
            audit_type=AuditType.EVENT_PROCESSED,
            status=AuditStatus.SUCCESS,
            component="event_consumer",
            event_id=event_id,
            event_type="attendance.marked",
            entity_type="attendance",
            entity_id="ATT-DB-TEST",
        )
        assert created is not None
        assert created.id is not None
        assert created.created_at is not None

        fetched = service.get_by_event(event_id)
        assert len(fetched) == 1
        assert fetched[0].event_id == event_id

        by_id = service.get_by_id(created.id)
        assert by_id is not None
        assert by_id.id == created.id
    finally:
        db.close()


@requires_db
def test_audit_api_trace_endpoint_returns_records_for_triggered_event():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/automation/dummy-events/attendance-marked",
        json={"student_id": "STU-AUDIT-API", "attendance_percentage": 30},
    )
    assert resp.status_code == 200
    event_id = resp.json()["event_id"]

    trace_resp = client.get(f"/audit/event/{event_id}")
    assert trace_resp.status_code == 200
    records = trace_resp.json()
    assert len(records) > 0
    assert all(r["event_id"] == event_id for r in records)
    audit_types = {r["audit_type"] for r in records}
    assert "EVENT_PROCESSED" in audit_types
    assert "WORKFLOW_EXECUTED" in audit_types
