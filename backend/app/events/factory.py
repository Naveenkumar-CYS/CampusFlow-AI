"""
Settings-driven construction of an EventBus.

Kept separate from bus.py / redis_bus.py so that importing the EventBus
interface or InMemoryEventBus (e.g. from tests) never requires the
`redis` package to be importable -- only get_redis_event_bus() below
touches redis_bus.py.
"""
from __future__ import annotations

from app.core.config import Settings, get_settings
from app.events.redis_bus import RedisStreamEventBus


def get_redis_event_bus(settings: Settings | None = None) -> RedisStreamEventBus:
    """Build a RedisStreamEventBus from the app's Settings (REDIS_URL,
    REDIS_STREAM_NAME, REDIS_CONSUMER_GROUP, REDIS_CONSUMER_NAME).

    Does not connect eagerly or create the consumer group -- callers
    should call `create_consumer_group()` once at worker startup.
    """
    settings = settings or get_settings()
    return RedisStreamEventBus(
        redis_url=settings.redis_url,
        stream_name=settings.redis_stream_name,
        group_name=settings.redis_consumer_group,
        consumer_name=settings.redis_consumer_name,
    )
