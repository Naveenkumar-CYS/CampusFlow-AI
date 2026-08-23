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
"""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.automation.events import CanonicalEvent, EventValidationError
from app.automation.rules import RuleEngine
from app.automation.store import ExecutionStore
from app.automation.workflows import WorkflowEngine


class EventConsumer:
    def __init__(
        self,
        rule_engine: RuleEngine,
        workflow_engine: WorkflowEngine,
        store: ExecutionStore,
    ):
        self._rules = rule_engine
        self._workflows = workflow_engine
        self._store = store

    def consume(self, raw_event: dict[str, Any] | CanonicalEvent) -> "ConsumeResult":
        event = self._to_canonical(raw_event)

        if self._store.was_already_processed(event.event_id):
            return ConsumeResult(
                event=event, status="skipped_duplicate", workflow_run=None
            )

        rule = self._rules.match(event)
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
