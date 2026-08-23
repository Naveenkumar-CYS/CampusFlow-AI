"""
Redis Streams implementation of EventBus.

Uses Redis consumer groups (XGROUP/XREADGROUP/XACK) so multiple worker
processes can share a stream with at-least-once delivery and an explicit
ack step, matching the EventBus contract in events/bus.py.

This module is the ONLY place in the codebase that imports `redis`.
Nothing in app.automation.* (RuleEngine, WorkflowEngine, EventConsumer)
knows this class exists -- they only ever see a CanonicalEvent, handed
to them by whatever reads off the bus (see events/runner.py). That
keeps the Rule Engine transport-agnostic per the Stage 1 brief.
"""
from __future__ import annotations

import logging

import redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError, ResponseError

from app.automation.events import CanonicalEvent
from app.events.bus import (
    PAYLOAD_FIELD,
    EventBus,
    EventBusConnectionError,
    EventBusError,
    StreamMessage,
    deserialize_stream_fields,
)

logger = logging.getLogger("campusflow.events.redis_bus")

# Redis returns "BUSYGROUP Consumer Group name already exists" when the
# group already exists -- that's the expected, idempotent case for
# create_consumer_group(), not an error.
_BUSYGROUP_PREFIX = "BUSYGROUP"


class RedisStreamEventBus(EventBus):
    """EventBus backed by a Redis Stream + consumer group.

    One instance corresponds to one (stream, consumer group, consumer
    name) triple -- i.e. one logical worker. Multiple instances with the
    same stream/group but different consumer names can run concurrently
    for horizontal scaling; Redis divides pending messages between them.
    """

    def __init__(
        self,
        redis_url: str,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        *,
        client: "redis.Redis | None" = None,
        socket_timeout: float = 5.0,
    ) -> None:
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        # decode_responses=True so field/value pairs come back as str,
        # not bytes -- CanonicalEvent.model_validate_json wants str/bytes
        # either way, but str keeps deserialize_stream_fields simple.
        self._redis = client or redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_timeout,
        )

    def ping(self) -> bool:
        """Cheap connectivity check, e.g. for health endpoints / startup
        probes. Raises EventBusConnectionError if Redis is unreachable."""
        try:
            return bool(self._redis.ping())
        except RedisConnectionError as exc:
            raise EventBusConnectionError(f"cannot reach Redis: {exc}") from exc

    def create_consumer_group(self) -> None:
        try:
            # mkstream=True: create the stream itself if it doesn't
            # exist yet, so a consumer can start up before any producer
            # has published anything.
            self._redis.xgroup_create(
                name=self.stream_name, groupname=self.group_name, id="0", mkstream=True
            )
        except ResponseError as exc:
            if str(exc).startswith(_BUSYGROUP_PREFIX):
                # Already exists -- exactly what we want, idempotent no-op.
                return
            raise EventBusError(f"failed to create consumer group: {exc}") from exc
        except RedisConnectionError as exc:
            raise EventBusConnectionError(f"cannot reach Redis: {exc}") from exc

    def publish(self, event: CanonicalEvent) -> str:
        try:
            message_id = self._redis.xadd(
                self.stream_name, {PAYLOAD_FIELD: event.model_dump_json()}
            )
        except RedisConnectionError as exc:
            raise EventBusConnectionError(f"cannot reach Redis: {exc}") from exc
        except RedisError as exc:
            raise EventBusError(f"failed to publish event: {exc}") from exc
        return message_id

    def consume(self, count: int = 10, block_ms: int = 1000) -> list[StreamMessage]:
        try:
            # ">" means "only new messages this consumer hasn't seen",
            # i.e. normal at-least-once consumption. Reading this
            # consumer's own already-pending (un-acked) entries would use
            # a real message id instead of ">" -- deliberately not done
            # automatically here so a stuck message doesn't silently
            # loop forever without operator visibility; that's a Stage 2+
            # concern (dead-lettering off the bus itself).
            response = self._redis.xreadgroup(
                groupname=self.group_name,
                consumername=self.consumer_name,
                streams={self.stream_name: ">"},
                count=count,
                block=block_ms,
            )
        except ResponseError as exc:
            if "NOGROUP" in str(exc):
                # Consumer group vanished or was never created -- surface
                # a clear error rather than a cryptic Redis exception.
                raise EventBusError(
                    f"consumer group {self.group_name!r} does not exist on "
                    f"stream {self.stream_name!r} -- call create_consumer_group() first"
                ) from exc
            raise EventBusError(f"failed to read from stream: {exc}") from exc
        except RedisConnectionError as exc:
            raise EventBusConnectionError(f"cannot reach Redis: {exc}") from exc

        if not response:
            return []

        messages: list[StreamMessage] = []
        # response shape: [(stream_name, [(message_id, fields), ...])]
        for _stream_name, entries in response:
            for message_id, fields in entries:
                event, error = deserialize_stream_fields(fields)
                messages.append(
                    StreamMessage(message_id=message_id, event=event, raw=fields, error=error)
                )
                if error:
                    logger.warning(
                        "malformed message on stream=%s group=%s id=%s: %s",
                        self.stream_name,
                        self.group_name,
                        message_id,
                        error,
                    )
        return messages

    def ack(self, message_id: str) -> None:
        try:
            self._redis.xack(self.stream_name, self.group_name, message_id)
        except RedisConnectionError as exc:
            raise EventBusConnectionError(f"cannot reach Redis: {exc}") from exc
        except RedisError as exc:
            raise EventBusError(f"failed to ack message {message_id!r}: {exc}") from exc

    def close(self) -> None:
        try:
            self._redis.close()
        except RedisError:
            pass
