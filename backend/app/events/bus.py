"""
Event Bus abstraction.

This is the transport-agnostic contract used to move CanonicalEvent
instances (see app.automation.events) between producers and Person B's
automation backbone (EventConsumer / RuleEngine / WorkflowEngine).

Design intent:

    - The Rule Engine and Workflow Engine NEVER import Redis, or any
      transport, directly. They only ever see a CanonicalEvent, handed
      to them by EventConsumer.consume(). That stays true after this
      module exists.
    - EventBus is the seam. Anything that reads off a bus is
      responsible for turning a StreamMessage into a CanonicalEvent and
      calling EventConsumer.consume() with it -- see events/runner.py.
    - Two implementations ship in this stage:
        * InMemoryEventBus  -- no external dependency. Used by unit
          tests and local dev without Redis running. Also useful as a
          drop-in fake for anything that depends on EventBus.
        * RedisStreamEventBus (see events/redis_bus.py) -- the real
          Redis Streams + consumer-group backed transport.

The existing manual/direct automation trigger paths (app/api/automation.py,
app/events/publisher.py) are untouched by this module -- they call
EventConsumer.consume() directly and continue to work exactly as before.
The event bus is an additional, opt-in transport, not a replacement for
those paths in this stage.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.automation.events import CanonicalEvent

logger = logging.getLogger("campusflow.events.bus")

# Single field name used to store the CanonicalEvent's JSON payload
# inside a stream entry. Streams are field->value maps, not raw
# strings, so we keep the entry shape to one well-known field rather
# than exploding CanonicalEvent's own fields into the stream schema --
# that keeps the transport layer decoupled from the envelope's shape.
PAYLOAD_FIELD = "event"


@dataclass
class StreamMessage:
    """A single message read off an EventBus, paired with the
    transport-level message id needed to ack() it later.

    `event` is None when the raw entry could not be turned into a
    CanonicalEvent (missing field, invalid JSON, failed validation) --
    callers must check `is_malformed` before using `event` and should
    still ack() (or explicitly dead-letter) malformed messages so a
    poison-pill entry doesn't get redelivered forever.
    """

    message_id: str
    event: CanonicalEvent | None
    raw: dict[str, Any]
    error: str | None = None

    @property
    def is_malformed(self) -> bool:
        return self.event is None


class EventBusError(Exception):
    """Base class for event bus failures."""


class EventBusConnectionError(EventBusError):
    """Raised when the bus cannot reach its backing transport (e.g. Redis
    is unreachable). Distinct from EventBusError so callers can decide to
    retry/backoff on connection failures specifically."""


def deserialize_stream_fields(fields: dict[str, Any]) -> tuple[CanonicalEvent | None, str | None]:
    """Shared malformed-message handling for any transport whose entries
    are field->value maps with the payload under PAYLOAD_FIELD.

    Returns (event, error) -- exactly one of which is non-None.
    """
    raw_payload = fields.get(PAYLOAD_FIELD)
    if raw_payload is None:
        return None, f"stream entry missing '{PAYLOAD_FIELD}' field: {fields!r}"

    try:
        event = CanonicalEvent.model_validate_json(raw_payload)
    except (ValidationError, ValueError, TypeError) as exc:
        return None, f"failed to parse CanonicalEvent from stream entry: {exc}"

    return event, None


class EventBus(ABC):
    """Transport-agnostic publish/consume interface for CanonicalEvent.

    Consumer-group semantics (at-least-once delivery, per-consumer
    read cursor, explicit ack) are part of the contract even for
    InMemoryEventBus, so tests written against the interface exercise
    the same behavior a Redis-backed consumer will see in production.
    """

    @abstractmethod
    def publish(self, event: CanonicalEvent) -> str:
        """Publish a CanonicalEvent. Returns the transport message id."""

    @abstractmethod
    def create_consumer_group(self) -> None:
        """Idempotently ensure the stream and consumer group exist.
        Safe to call every time a consumer starts up."""

    @abstractmethod
    def consume(self, count: int = 10, block_ms: int = 1000) -> list[StreamMessage]:
        """Read up to `count` new messages for this bus's consumer group
        + consumer name. Malformed entries are returned as StreamMessage
        with is_malformed=True rather than raised, so one bad message
        doesn't block the whole batch."""

    @abstractmethod
    def ack(self, message_id: str) -> None:
        """Acknowledge successful processing of a message, removing it
        from the consumer group's pending-entries list."""


class InMemoryEventBus(EventBus):
    """In-process fake, no Redis required.

    Approximates Redis Streams consumer-group semantics closely enough
    to be a useful test double:
        - publish() appends to an ordered log with monotonically
          increasing message ids.
        - consume() only returns messages the calling consumer group
          hasn't already been delivered, and moves them into a
          "pending" set until ack()'d (mirrors XREADGROUP + PEL).
        - ack() removes a message id from that group's pending set.

    Intended for unit tests and for running the automation chain
    locally without a Redis instance -- NOT a substitute for the real
    RedisStreamEventBus in any deployed environment.
    """

    def __init__(
        self,
        stream_name: str = "campusflow.events",
        group_name: str = "campusflow-automation",
    ) -> None:
        self.stream_name = stream_name
        self.group_name = group_name
        self._log: list[tuple[str, dict[str, Any]]] = []
        # group_name -> next index into self._log not yet delivered
        self._cursors: dict[str, int] = {}
        # group_name -> {message_id: fields} still awaiting ack
        self._pending: dict[str, dict[str, dict[str, Any]]] = {}
        self._groups_created: set[str] = set()

    def create_consumer_group(self) -> None:
        self._cursors.setdefault(self.group_name, 0)
        self._pending.setdefault(self.group_name, {})
        self._groups_created.add(self.group_name)

    def publish(self, event: CanonicalEvent) -> str:
        message_id = f"{len(self._log)}-0"
        fields = {PAYLOAD_FIELD: event.model_dump_json()}
        self._log.append((message_id, fields))
        return message_id

    def publish_raw(self, fields: dict[str, Any]) -> str:
        """Test/debug hook: publish an already-malformed or arbitrary
        field map directly, bypassing CanonicalEvent entirely. Mirrors
        what happens if a non-conforming producer (or Redis CLI) writes
        straight to the stream."""
        message_id = f"{len(self._log)}-0"
        self._log.append((message_id, dict(fields)))
        return message_id

    def consume(self, count: int = 10, block_ms: int = 1000) -> list[StreamMessage]:
        self.create_consumer_group()
        cursor = self._cursors[self.group_name]
        batch = self._log[cursor : cursor + count]
        self._cursors[self.group_name] = cursor + len(batch)

        messages: list[StreamMessage] = []
        for message_id, fields in batch:
            event, error = deserialize_stream_fields(fields)
            self._pending[self.group_name][message_id] = fields
            messages.append(
                StreamMessage(message_id=message_id, event=event, raw=fields, error=error)
            )
            if error:
                logger.warning(
                    "malformed message on stream=%s id=%s: %s",
                    self.stream_name,
                    message_id,
                    error,
                )
        return messages

    def ack(self, message_id: str) -> None:
        self._pending.setdefault(self.group_name, {}).pop(message_id, None)

    def pending_count(self) -> int:
        return len(self._pending.get(self.group_name, {}))

    def reset(self) -> None:
        """Test convenience: wipe all state."""
        self._log.clear()
        self._cursors.clear()
        self._pending.clear()
        self._groups_created.clear()
