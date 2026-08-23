"""
Bus runner -- the bridge between an EventBus and the existing automation
backbone (EventConsumer -> RuleEngine -> WorkflowEngine).

Nothing in app.automation.* changes to support this: EventConsumer
already accepts a CanonicalEvent (see consumer.py), which is exactly
what StreamMessage.event is once a message is read off the bus. This
module just loops read -> hand off -> ack, and is the only place that
needs to know both "there's a bus" and "there's an automation engine".

This is a foundation piece for Stage 1, not a production worker process
(no supervisord/systemd wiring, no graceful shutdown handling beyond
`max_iterations`) -- running it long-lived is future work.
"""
from __future__ import annotations

import logging

from app.automation.consumer import ConsumeResult, EventConsumer
from app.events.bus import EventBus, StreamMessage

logger = logging.getLogger("campusflow.events.runner")


class EventBusRunner:
    """Pulls messages off an EventBus and feeds them through an
    EventConsumer, acknowledging each message once handled.

    Malformed messages are logged and acked immediately (not retried --
    there's no valid CanonicalEvent to retry with) rather than left
    pending forever, which would otherwise wedge the consumer group.
    """

    def __init__(self, bus: EventBus, consumer: EventConsumer) -> None:
        self._bus = bus
        self._consumer = consumer

    def run_once(self, count: int = 10, block_ms: int = 1000) -> list[ConsumeResult | None]:
        """Read one batch, process it, ack every message. Returns one
        ConsumeResult per well-formed message (None for malformed ones,
        in the same order) so callers/tests can inspect outcomes."""
        self._bus.create_consumer_group()
        messages = self._bus.consume(count=count, block_ms=block_ms)

        results: list[ConsumeResult | None] = []
        for message in messages:
            results.append(self._handle(message))
        return results

    def _handle(self, message: StreamMessage) -> ConsumeResult | None:
        if message.is_malformed:
            logger.error(
                "dropping malformed message id=%s: %s", message.message_id, message.error
            )
            self._bus.ack(message.message_id)
            return None

        try:
            result = self._consumer.consume(message.event)
        except Exception:  # noqa: BLE001 -- one bad event must not wedge the runner
            logger.exception(
                "automation consume failed for event_id=%s (message_id=%s); "
                "leaving message un-acked for redelivery",
                message.event.event_id,
                message.message_id,
            )
            return None

        self._bus.ack(message.message_id)
        return result
