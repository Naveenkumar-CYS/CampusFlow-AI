"""
Automation backbone tests. Deliberately DB-free -- everything here runs
against InMemoryExecutionStore so the chain can be proven end-to-end
without a running Postgres instance. DbExecutionStore (the real,
Postgres-backed idempotency path) is exercised through the API layer and
is NOT covered here -- see README note on what's verified vs not.
"""
import pytest

from app.automation.actions import ACTION_REGISTRY, ActionExecutor, ActionResult, create_notification
from app.automation.consumer import EventConsumer
from app.automation.events import CanonicalEvent, EventValidationError
from app.automation.producer import make_attendance_marked_event, make_fee_paid_event
from app.automation.rules import Rule, RuleEngine
from app.automation.store import InMemoryExecutionStore
from app.automation.workflows import WorkflowEngine


def make_consumer():
    store = InMemoryExecutionStore()
    rule_engine = RuleEngine()
    workflow_engine = WorkflowEngine(store)
    return EventConsumer(rule_engine, workflow_engine, store), store


# ---------- Full chain ----------

def test_full_chain_attendance_warning_triggers_and_succeeds():
    consumer, store = make_consumer()
    event = make_attendance_marked_event(attendance_percentage=65)

    result = consumer.consume(event)

    assert result.status == "workflow_triggered"
    assert result.workflow_run.workflow_id == "attendance_warning"
    assert result.workflow_run.status == "success"

    action_names = [a.action for a in result.workflow_run.action_results]
    assert action_names == ["create_notification", "send_email", "send_sms", "record_execution"]
    assert all(a.status == "success" for a in result.workflow_run.action_results)


def test_full_chain_fee_paid_triggers_confirmation():
    consumer, _ = make_consumer()
    event = make_fee_paid_event(amount=1200.0)

    result = consumer.consume(event)

    assert result.status == "workflow_triggered"
    assert result.workflow_run.workflow_id == "fee_payment_confirmation"
    assert result.workflow_run.status == "success"


# ---------- Rule matching ----------

def test_high_attendance_does_not_match_rule():
    consumer, _ = make_consumer()
    event = make_attendance_marked_event(attendance_percentage=90)

    result = consumer.consume(event)

    assert result.status == "no_rule_matched"
    assert result.workflow_run is None


def test_disabled_rule_never_matches():
    store = InMemoryExecutionStore()
    disabled_rule = Rule(
        id="RULE-DISABLED",
        name="disabled",
        event_type=next(iter([e for e in [make_attendance_marked_event().event_type]])),
        condition=lambda data: True,
        workflow_id="attendance_warning",
        enabled=False,
    )
    consumer = EventConsumer(RuleEngine(rules=[disabled_rule]), WorkflowEngine(store), store)
    event = make_attendance_marked_event(attendance_percentage=10)

    result = consumer.consume(event)

    assert result.status == "no_rule_matched"


# ---------- Event validation ----------

def test_invalid_event_missing_required_field_raises():
    consumer, _ = make_consumer()
    with pytest.raises(EventValidationError):
        consumer.consume({"event_type": "attendance.marked"})  # missing aggregate_id, student_id etc.


def test_unknown_event_type_raises():
    consumer, _ = make_consumer()
    with pytest.raises(EventValidationError):
        consumer.consume(
            {
                "event_type": "totally.unknown",
                "aggregate_type": "x",
                "aggregate_id": "1",
                "student_id": "STU-001",
                "data": {},
            }
        )


def test_valid_raw_dict_event_is_accepted():
    consumer, _ = make_consumer()
    raw = {
        "event_type": "attendance.marked",
        "aggregate_type": "attendance",
        "aggregate_id": "ATT-002",
        "student_id": "STU-002",
        "data": {"subject_id": "SUB-1", "attendance_percentage": 50, "status": "ABSENT"},
    }
    result = consumer.consume(raw)
    assert result.status == "workflow_triggered"


# ---------- Idempotency ----------

def test_duplicate_event_id_is_not_reprocessed():
    consumer, store = make_consumer()
    event = make_attendance_marked_event(aggregate_id="ATT-DUP", attendance_percentage=50)

    first = consumer.consume(event)
    second = consumer.consume(event)  # same event_id, sent twice

    assert first.status == "workflow_triggered"
    assert second.status == "skipped_duplicate"
    assert second.workflow_run is None


# ---------- Retries ----------

def test_action_retries_then_fails_after_max_attempts():
    calls = {"n": 0}

    def flaky_action(event, context):
        calls["n"] += 1
        raise RuntimeError("simulated provider outage")

    executor = ActionExecutor(max_attempts=3, registry={"flaky": flaky_action})
    result = executor.execute("flaky", make_attendance_marked_event(), {})

    assert result.status == "failed"
    assert result.attempts == 3
    assert calls["n"] == 3


def test_action_succeeds_on_retry_after_transient_failure():
    calls = {"n": 0}

    def flaky_then_ok(event, context):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient")
        return {"ok": True}

    executor = ActionExecutor(max_attempts=3, registry={"flaky": flaky_then_ok})
    result = executor.execute("flaky", make_attendance_marked_event(), {})

    assert result.status == "success"
    assert result.attempts == 2


def test_workflow_stops_on_first_action_failure():
    store = InMemoryExecutionStore()

    def always_fails(event, context):
        raise RuntimeError("boom")

    executor = ActionExecutor(max_attempts=1, registry={"create_notification": always_fails})
    engine = WorkflowEngine(store, action_executor=executor)
    event = make_attendance_marked_event()

    run = engine.run("attendance_warning", event)

    assert run.status == "failed"
    # only the failing first step ran -- send_email/send_sms/record_execution never attempted
    assert [a.action for a in run.action_results] == ["create_notification"]


# ---------- Dead-letter retry ----------

def test_failed_execution_can_be_retried_and_succeeds_once_fixed():
    store = InMemoryExecutionStore()
    calls = {"n": 0}

    def create_notification_flaky_once(event, context):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated outage")
        return create_notification(event, context)

    registry = dict(ACTION_REGISTRY)
    registry["create_notification"] = create_notification_flaky_once
    executor = ActionExecutor(max_attempts=1, registry=registry)
    engine = WorkflowEngine(store, action_executor=executor)
    event = make_attendance_marked_event(aggregate_id="ATT-RETRY")

    first_run = engine.run("attendance_warning", event)
    assert first_run.status == "failed"

    dead_letters = store.get_dead_letters()
    assert len(dead_letters) == 1
    assert dead_letters[0].event_id == event.event_id

    retry_run = engine.retry(event.event_id)

    assert retry_run is not None
    assert retry_run.status == "success"  # fixed the second time around, full chain now completes
    assert calls["n"] == 2
    assert not store.get_dead_letters()  # no longer in the dead-letter list once it succeeds


def test_retry_returns_none_for_unknown_or_non_failed_event():
    store = InMemoryExecutionStore()
    engine = WorkflowEngine(store)

    assert engine.retry("no-such-event") is None

    # a successful run is not retryable
    event = make_attendance_marked_event(aggregate_id="ATT-OK", attendance_percentage=40)
    run = engine.run("attendance_warning", event)
    assert run.status == "success"
    assert engine.retry(event.event_id) is None
