"""
Event worker -- the standalone process that reads real domain events off
the Redis Stream and drives them through the existing automation chain
(EventConsumer -> RuleEngine -> WorkflowEngine -> ActionExecutor ->
NotificationService -> AuditService).

This is Step 3 of the integration: the FastAPI process and this worker
process are the two things that must both be running for
AUTOMATION_TRANSPORT=redis to actually deliver anything --

    Domain Service --publish()--> Redis Stream            (FastAPI process)
    Redis Stream --EventBusRunner--> EventConsumer -> ...  (THIS process)

Nothing in app.automation.* or app.events.bus/runner changes to support
this -- this module only wires existing pieces together and adds the
run-forever loop + a CLI entry point, neither of which existed before.

Usage (from backend/):

    python -m app.worker

Stops cleanly on SIGINT/SIGTERM (Ctrl+C, or however your process
manager stops it) -- finishes the in-flight batch, then exits instead of
dying mid-ack.
"""
from __future__ import annotations

import logging
import signal
import sys

from app.automation.consumer import EventConsumer
from app.automation.rules import RuleEngine
from app.automation.store import DbExecutionStore
from app.automation.workflows import WorkflowEngine
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.events.factory import get_redis_event_bus
from app.events.runner import EventBusRunner
from app.services.audit import AuditService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("campusflow.worker")

_shutdown_requested = False


def _handle_shutdown_signal(signum, _frame) -> None:
    global _shutdown_requested
    logger.info("received signal %s -- finishing current batch, then exiting", signum)
    _shutdown_requested = True


def _process_one_batch() -> int:
    """Open one DB session, drive one EventBusRunner.run_once() through
    it, close the session. A fresh session per batch (rather than one
    held open for the worker's whole lifetime) keeps a single bad/slow
    DB interaction from wedging every future batch, and matches how
    app.db.session.get_db already scopes a session to one unit of work
    everywhere else in this codebase.

    Returns the number of messages read (0 when the poll simply timed
    out with nothing new -- not an error)."""
    bus = get_redis_event_bus()
    db = SessionLocal()
    try:
        audit = AuditService(db)
        store = DbExecutionStore(db)
        consumer = EventConsumer(
            RuleEngine(), WorkflowEngine(store, db=db, audit_service=audit), store, audit_service=audit
        )
        runner = EventBusRunner(bus, consumer)
        results = runner.run_once(count=10, block_ms=5000)

        for result in results:
            if result is None:
                continue
            logger.info(
                "processed event_id=%s status=%s workflow_id=%s",
                result.event.event_id,
                result.status,
                result.workflow_run.workflow_id if result.workflow_run else None,
            )
        return len(results)
    finally:
        db.close()
        bus.close()


def run_forever() -> None:
    settings = get_settings()
    if settings.automation_transport != "redis":
        logger.warning(
            "AUTOMATION_TRANSPORT=%r -- domain services are publishing in-process, "
            "not via Redis, so this worker will sit idle. Set AUTOMATION_TRANSPORT=redis "
            "on the API process for events to actually reach this worker.",
            settings.automation_transport,
        )

    logger.info(
        "event worker starting: redis_url=%s stream=%s group=%s consumer=%s",
        settings.redis_url,
        settings.redis_stream_name,
        settings.redis_consumer_group,
        settings.redis_consumer_name,
    )

    # Ensure the consumer group exists before the first read -- safe to
    # call every startup (see RedisStreamEventBus.create_consumer_group).
    bootstrap_bus = get_redis_event_bus()
    bootstrap_bus.create_consumer_group()
    bootstrap_bus.close()

    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)

    logger.info("event worker ready, polling stream...")
    while not _shutdown_requested:
        try:
            _process_one_batch()
        except Exception:  # noqa: BLE001 -- one bad batch must not kill the worker process
            logger.exception("unhandled error while processing a batch; continuing")

    logger.info("event worker stopped")


def main() -> int:
    run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
