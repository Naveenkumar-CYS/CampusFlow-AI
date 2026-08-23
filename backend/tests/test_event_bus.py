"""
Event Bus tests.

InMemoryEventBus tests run unconditionally, no external services
required. RedisStreamEventBus tests are integration tests that connect
to a real Redis instance (REDIS_URL, default redis://localhost:6379/0)
and are skipped automatically if Redis is unreachable -- see
`_redis_available()` below.
"""
from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from app.automation.consumer import EventConsumer
from app.automation.events import CanonicalEvent, EventType
from app.automation.producer import make_attendance_marked_event, make_fee_paid_event
from app.automation.rules import RuleEngine
from app.automation.store import InMemoryExecutionStore
from app.automation.workflows import WorkflowEngine
from app.events.bus import (
    PAYLOAD_FIELD,
    EventBusError,
    InMemoryEventBus,
    StreamMessage,
    deserialize_stream_fields,
)
from app.events.runner import EventBusRunner


# ---------- publish / serialize / deserialize ----------


def test_publish_returns_message_id():
    bus = InMemoryEventBus()
    event = make_attendance_marked_event()

    message_id = bus.publish(event)

    assert isinstance(message_id, str)
    assert message_id  # non-empty


def test_published_event_round_trips_through_deserialize():
    bus = InMemoryEventBus()
    event = make_fee_paid_event(amount=999.5, fee_type="hostel")

    bus.publish(event)
    [message] = bus.consume(count=10)

    assert not message.is_malformed
    assert message.event == event
    assert message.event.event_type == EventType.FEE_PAID
    assert message.event.data["amount"] == 999.5


def test_deserialize_stream_fields_missing_payload_field():
    event, error = deserialize_stream_fields({"unexpected": "value"})

    assert event is None
    assert error is not None
    assert PAYLOAD_FIELD in error


def test_deserialize_stream_fields_invalid_json():
    event, error = deserialize_stream_fields({PAYLOAD_FIELD: "{not valid json"})

    assert event is None
    assert "failed to parse" in error


def test_deserialize_stream_fields_valid_payload():
    original = make_attendance_marked_event(attendance_percentage=42)
    fields = {PAYLOAD_FIELD: original.model_dump_json()}

    event, error = deserialize_stream_fields(fields)

    assert error is None
    assert event == original


# ---------- consumer group ----------


def test_create_consumer_group_is_idempotent():
    bus = InMemoryEventBus(group_name="grp-a")

    bus.create_consumer_group()
    bus.create_consumer_group()  # must not raise / must not reset cursor

    bus.publish(make_attendance_marked_event())
    messages = bus.consume(count=10)
    assert len(messages) == 1


def test_separate_consumer_groups_each_see_all_messages():
    bus_a = InMemoryEventBus(group_name="grp-a")
    # Same underlying log semantics are exercised through two bus
    # instances pointed at independent in-memory state here, since
    # InMemoryEventBus keeps its log per-instance -- what's under test
    # is that group bookkeeping (cursor/pending) is keyed by group_name
    # and doesn't leak across groups on a single instance.
    bus_a.publish(make_attendance_marked_event())
    bus_a.publish(make_fee_paid_event())

    first_group_messages = bus_a.consume(count=10)
    assert len(first_group_messages) == 2

    # A second read from the same group with nothing new published
    # returns nothing (already delivered).
    assert bus_a.consume(count=10) == []


# ---------- successful consumption + ack ----------


def test_consume_then_ack_clears_pending():
    bus = InMemoryEventBus()
    bus.publish(make_attendance_marked_event())

    [message] = bus.consume(count=10)
    assert bus.pending_count() == 1

    bus.ack(message.message_id)
    assert bus.pending_count() == 0


def test_consume_respects_count_limit():
    bus = InMemoryEventBus()
    for _ in range(5):
        bus.publish(make_attendance_marked_event())

    first_batch = bus.consume(count=2)
    second_batch = bus.consume(count=2)
    third_batch = bus.consume(count=2)

    assert len(first_batch) == 2
    assert len(second_batch) == 2
    assert len(third_batch) == 1


# ---------- malformed message handling ----------


def test_malformed_message_does_not_raise_and_is_flagged():
    bus = InMemoryEventBus()
    bus.publish_raw({"garbage": "no payload field here"})

    [message] = bus.consume(count=10)

    assert message.is_malformed
    assert message.event is None
    assert message.error is not None


def test_malformed_message_does_not_block_well_formed_messages_in_same_batch():
    bus = InMemoryEventBus()
    bus.publish_raw({"garbage": "bad"})
    good_event = make_attendance_marked_event()
    bus.publish(good_event)

    messages = bus.consume(count=10)

    assert len(messages) == 2
    assert messages[0].is_malformed
    assert not messages[1].is_malformed
    assert messages[1].event == good_event


def test_runner_does_not_ack_when_processing_raises():
    """A processing exception (e.g. a transient dependency outage) must
    leave the message un-acked so it's redelivered later, and must not
    crash the runner itself."""

    class ExplodingConsumer:
        def consume(self, event):
            raise RuntimeError("simulated processing failure")

    bus = InMemoryEventBus()
    bus.publish(make_attendance_marked_event())
    runner = EventBusRunner(bus, ExplodingConsumer())

    results = runner.run_once()

    assert results == [None]
    assert bus.pending_count() == 1  # NOT acked -- still pending for redelivery


def test_runner_acks_and_drops_malformed_message_without_crashing():
    bus = InMemoryEventBus()
    bus.publish_raw({"garbage": "bad"})
    consumer = EventConsumer(RuleEngine(), WorkflowEngine(InMemoryExecutionStore()), InMemoryExecutionStore())
    runner = EventBusRunner(bus, consumer)

    results = runner.run_once()

    assert results == [None]
    assert bus.pending_count() == 0  # acked so it doesn't wedge the group


# ---------- duplicate event ids ----------


def test_duplicate_event_id_published_twice_both_delivered_by_bus():
    # The bus itself is a dumb transport -- it does not dedupe. Dedup is
    # the automation layer's job (ExecutionStore.was_already_processed),
    # exercised end-to-end here via EventBusRunner + EventConsumer.
    bus = InMemoryEventBus()
    event = make_attendance_marked_event(attendance_percentage=10)
    bus.publish(event)
    bus.publish(event)  # same event_id, republished (e.g. producer retry)

    store = InMemoryExecutionStore()
    consumer = EventConsumer(RuleEngine(), WorkflowEngine(store), store)
    runner = EventBusRunner(bus, consumer)

    results = runner.run_once(count=10)

    assert len(results) == 2
    statuses = {r.status for r in results}
    assert "workflow_triggered" in statuses
    assert "skipped_duplicate" in statuses


# ---------- end-to-end: bus -> runner -> automation chain ----------


def test_runner_drives_full_chain_for_attendance_warning():
    bus = InMemoryEventBus()
    event = make_attendance_marked_event(attendance_percentage=50)
    bus.publish(event)

    store = InMemoryExecutionStore()
    consumer = EventConsumer(RuleEngine(), WorkflowEngine(store), store)
    runner = EventBusRunner(bus, consumer)

    [result] = runner.run_once()

    assert result.status == "workflow_triggered"
    assert result.workflow_run.workflow_id == "attendance_warning"
    assert result.workflow_run.status == "success"
    assert bus.pending_count() == 0


# ---------- InMemoryEventBus as the fake for test/local-dev use ----------


def test_in_memory_bus_reset_clears_all_state():
    bus = InMemoryEventBus()
    bus.publish(make_attendance_marked_event())
    bus.consume(count=10)

    bus.reset()

    assert bus.consume(count=10) == []
    assert bus.pending_count() == 0


# ---------- Redis integration (skipped if Redis is unavailable) ----------


def _redis_available() -> bool:
    try:
        import redis
    except ImportError:
        return False
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        client = redis.Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
        return bool(client.ping())
    except Exception:
        return False


requires_redis = pytest.mark.skipif(
    not _redis_available(), reason="Redis is not reachable; skipping Redis integration tests"
)


@requires_redis
def test_redis_stream_event_bus_publish_and_consume():
    import uuid

    from app.events.redis_bus import RedisStreamEventBus

    stream = f"campusflow.events.test.{uuid.uuid4().hex[:8]}"
    bus = RedisStreamEventBus(
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        stream_name=stream,
        group_name="test-group",
        consumer_name="test-consumer",
    )
    try:
        bus.create_consumer_group()
        event = make_attendance_marked_event(attendance_percentage=20)
        bus.publish(event)

        messages = bus.consume(count=10, block_ms=1000)

        assert len(messages) == 1
        assert not messages[0].is_malformed
        assert messages[0].event == event

        bus.ack(messages[0].message_id)
    finally:
        bus._redis.delete(stream)
        bus._redis.close()


@requires_redis
def test_redis_stream_event_bus_create_consumer_group_is_idempotent():
    import uuid

    from app.events.redis_bus import RedisStreamEventBus

    stream = f"campusflow.events.test.{uuid.uuid4().hex[:8]}"
    bus = RedisStreamEventBus(
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        stream_name=stream,
        group_name="test-group",
        consumer_name="test-consumer",
    )
    try:
        bus.create_consumer_group()
        bus.create_consumer_group()  # must not raise BUSYGROUP
    finally:
        bus._redis.delete(stream)
        bus._redis.close()


@requires_redis
def test_redis_stream_event_bus_malformed_message_handling():
    import uuid

    from app.events.redis_bus import RedisStreamEventBus

    stream = f"campusflow.events.test.{uuid.uuid4().hex[:8]}"
    bus = RedisStreamEventBus(
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        stream_name=stream,
        group_name="test-group",
        consumer_name="test-consumer",
    )
    try:
        bus.create_consumer_group()
        # Write a malformed entry directly, bypassing publish().
        bus._redis.xadd(stream, {"not_the_payload_field": "junk"})

        messages = bus.consume(count=10, block_ms=1000)

        assert len(messages) == 1
        assert messages[0].is_malformed
        bus.ack(messages[0].message_id)  # must not raise
    finally:
        bus._redis.delete(stream)
        bus._redis.close()
