"""
Execution Store.

Two responsibilities that live together deliberately: idempotency
(has this event_id already produced an Execution?) and the audit/trace
log (execution + per-action records, queryable by event_id per Step 13).
A third responsibility rides along: persisting the original event
payload, which is what makes dead-letter retry possible -- a failed
execution can be re-run later without the producer resending it.

Two implementations behind the same interface:

    - InMemoryExecutionStore: no DB required. Used by tests and by the
      dummy-producer smoke test so the chain can be proven end-to-end
      without a running Postgres instance.
    - DbExecutionStore: wraps the real repositories/execution.py and
      persists through the existing SQLAlchemy session. This is what the
      API layer uses.

Swapping which one the WorkflowEngine/EventConsumer are built with is a
constructor argument, not a code change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from app.automation.events import CanonicalEvent


@dataclass
class ExecutionRecord:
    event_id: str
    workflow_id: str
    status: str = "running"  # running | success | failed
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    error: str | None = None
    action_log: list[dict] = field(default_factory=list)


class ExecutionStore(Protocol):
    def was_already_processed(self, event_id: str) -> bool: ...

    def start_execution(self, event: CanonicalEvent, workflow_id: str) -> ExecutionRecord: ...

    def record_action(
        self,
        record: ExecutionRecord,
        action_type: str,
        status: str,
        attempt: int,
        error: str | None = None,
    ) -> None: ...

    def complete_execution(
        self, record: ExecutionRecord, status: str, error: str | None = None
    ) -> None: ...


class InMemoryExecutionStore:
    def __init__(self) -> None:
        self._by_event_id: dict[str, ExecutionRecord] = {}
        self._events_by_id: dict[str, CanonicalEvent] = {}

    def was_already_processed(self, event_id: str) -> bool:
        return event_id in self._by_event_id

    def start_execution(self, event: CanonicalEvent, workflow_id: str) -> ExecutionRecord:
        if event.event_id in self._by_event_id:
            # Should be caught upstream by was_already_processed, but stay
            # safe against races within a single process too.
            return self._by_event_id[event.event_id]
        record = ExecutionRecord(event_id=event.event_id, workflow_id=workflow_id)
        self._by_event_id[event.event_id] = record
        self._events_by_id[event.event_id] = event
        return record

    def record_action(self, record, action_type, status, attempt, error=None) -> None:
        record.action_log.append(
            {"action_type": action_type, "status": status, "attempt": attempt, "error": error}
        )

    def complete_execution(self, record, status, error=None) -> None:
        record.status = status
        record.completed_at = datetime.now(timezone.utc)
        record.error = error

    def get_dead_letters(self) -> list[ExecutionRecord]:
        return [r for r in self._by_event_id.values() if r.status == "failed"]

    def get_event_for_retry(self, event_id: str) -> tuple[ExecutionRecord, CanonicalEvent] | None:
        record = self._by_event_id.get(event_id)
        if record is None or record.status != "failed":
            return None
        return record, self._events_by_id[event_id]


class DbExecutionStore:
    """Postgres-backed store. Idempotency relies on the unique index on
    automation_executions.event_id (see app/models/execution.py) as the
    source of truth, not just the in-app check -- was_already_processed()
    can race between two callers, but repositories.execution.create_running
    catches the resulting IntegrityError and returns the row that actually
    won the insert, so a race never surfaces as an unhandled crash or a
    second Execution row for the same event_id."""

    def __init__(self, db):
        from app.repositories import execution as execution_repo

        self._db = db
        self._repo = execution_repo

    def was_already_processed(self, event_id: str) -> bool:
        return self._repo.get_by_event_id(self._db, event_id) is not None

    def start_execution(self, event: CanonicalEvent, workflow_id: str) -> ExecutionRecord:
        db_execution = self._repo.create_running(
            self._db, event.event_id, workflow_id, event.model_dump_json()
        )
        record = ExecutionRecord(event_id=event.event_id, workflow_id=workflow_id)
        record._db_execution = db_execution  # noqa: SLF001 -- internal linkage only
        return record

    def record_action(self, record, action_type, status, attempt, error=None) -> None:
        self._repo.add_action_execution(
            self._db, record._db_execution, action_type, status, attempt, error
        )
        record.action_log.append(
            {"action_type": action_type, "status": status, "attempt": attempt, "error": error}
        )

    def complete_execution(self, record, status, error=None) -> None:
        self._repo.mark_completed(self._db, record._db_execution, status, error)
        record.status = status

    def get_event_for_retry(self, event_id: str) -> tuple[ExecutionRecord, CanonicalEvent] | None:
        """Fetch a failed execution + its original event, and reset the
        existing DB row to `running` in place -- retry re-runs the same
        execution row (new action_execution rows get appended as history)
        rather than creating a second Execution, which the unique index
        on event_id would reject anyway."""
        db_execution = self._repo.get_by_event_id(self._db, event_id)
        if db_execution is None or db_execution.status != "failed":
            return None

        event = CanonicalEvent.model_validate_json(db_execution.event_payload)
        db_execution = self._repo.reset_to_running(self._db, db_execution)

        record = ExecutionRecord(event_id=event_id, workflow_id=db_execution.workflow_id)
        record._db_execution = db_execution  # noqa: SLF001
        return record, event
