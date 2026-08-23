"""
Event Consumer.

Receives raw dicts (what a real transport would hand you) OR an already-
built CanonicalEvent (what the dummy producer hands you directly), and
does exactly three things:

    1. validate envelope
    2. check event type is known
    3. hand off to the rule engine

No business logic lives here. It does not know what attendance_warning
is, and it must not learn.

Stage 6: an optional `audit_service` records EVENT_PROCESSED and
RULE_EVALUATED audit entries (see app/services/audit.py). This is
additive only -- `audit_service` defaults to None (existing callers/tests
that construct EventConsumer without it are unaffected), and
AuditService.record() never raises, so a slow/unavailable audit DB can
never change consume()'s return value or block the rule/workflow path.
"""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.automation.events import CanonicalEvent, EventValidationError
from app.automation.rules import RuleEngine
from app.automation.store import ExecutionStore
from app.automation.workflows import WorkflowEngine
from app.schemas.audit import AuditStatus, AuditType


class EventConsumer:
    def __init__(
        self,
        rule_engine: RuleEngine,
        workflow_engine: WorkflowEngine,
        store: ExecutionStore,
        audit_service: Any | None = None,
    ):
        self._rules = rule_engine
        self._workflows = workflow_engine
        self._store = store
        self._audit = audit_service

    def consume(self, raw_event: dict[str, Any] | CanonicalEvent) -> "ConsumeResult":
        event = self._to_canonical(raw_event)

        if self._audit is not None:
            self._audit.record(
                audit_type=AuditType.EVENT_PROCESSED,
                status=AuditStatus.SUCCESS,
                component="event_consumer",
                event_id=event.event_id,
                event_type=event.event_type.value,
                entity_type=event.aggregate_type,
                entity_id=event.aggregate_id,
            )

        if self._store.was_already_processed(event.event_id):
            if self._audit is not None:
                self._audit.record(
                    audit_type=AuditType.RULE_EVALUATED,
                    status=AuditStatus.SKIPPED,
                    component="event_consumer",
                    event_id=event.event_id,
                    event_type=event.event_type.value,
                    context={"reason": "duplicate_event"},
                )
            return ConsumeResult(
                event=event, status="skipped_duplicate", workflow_run=None
            )

        rule = self._rules.match(event)
        if self._audit is not None:
            self._audit.record(
                audit_type=AuditType.RULE_EVALUATED,
                status=AuditStatus.SUCCESS if rule is not None else AuditStatus.SKIPPED,
                component="rule_engine",
                event_id=event.event_id,
                workflow_id=rule.workflow_id if rule is not None else None,
                event_type=event.event_type.value,
                action=rule.id if rule is not None else None,
                context=None if rule is not None else {"reason": "no_rule_matched"},
            )

        if rule is None:
            return ConsumeResult(event=event, status="no_rule_matched", workflow_run=None)

        run = self._workflows.run(rule.workflow_id, event)
        return ConsumeResult(event=event, status="workflow_triggered", workflow_run=run)

    @staticmethod
    def _to_canonical(raw_event: dict[str, Any] | CanonicalEvent) -> CanonicalEvent:
        if isinstance(raw_event, CanonicalEvent):
            return raw_event
        try:
            return CanonicalEvent.model_validate(raw_event)
        except ValidationError as exc:
            raise EventValidationError(str(exc), raw=raw_event) from exc


class ConsumeResult:
    """Small result wrapper so the API layer can report what happened."""

    def __init__(self, event: CanonicalEvent, status: str, workflow_run):
        self.event = event
        self.status = status  # "workflow_triggered" | "no_rule_matched" | "skipped_duplicate"
        self.workflow_run = workflow_run
