"""
Workflow Engine.

Orchestrates an ordered list of actions. Does NOT implement email/SMS
itself -- that's actions.py's job via NotificationService. Wraps the run
in the ExecutionStore so every run is traceable by event_id (Step 13) and
so a duplicate event_id never re-runs a workflow (Step 11).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.automation.actions import ActionExecutor, ActionResult
from app.automation.events import CanonicalEvent
from app.automation.notifications import NotificationService
from app.automation.store import ExecutionRecord, ExecutionStore

logger = logging.getLogger("campusflow.automation.workflow")


@dataclass(frozen=True)
class WorkflowStep:
    order: int
    action: str


@dataclass(frozen=True)
class Workflow:
    workflow_id: str
    name: str
    steps: list[WorkflowStep]
    enabled: bool = True


WORKFLOW_CATALOG: dict[str, Workflow] = {
    "attendance_warning": Workflow(
        workflow_id="attendance_warning",
        name="Low Attendance Warning",
        steps=[
            WorkflowStep(1, "create_notification"),
            WorkflowStep(2, "send_email"),
            WorkflowStep(3, "send_sms"),
            WorkflowStep(4, "record_execution"),
        ],
    ),
    "fee_payment_confirmation": Workflow(
        workflow_id="fee_payment_confirmation",
        name="Fee Payment Confirmation",
        steps=[
            WorkflowStep(1, "create_notification"),
            WorkflowStep(2, "send_email"),
            WorkflowStep(3, "record_execution"),
        ],
    ),
}


@dataclass
class WorkflowRun:
    event_id: str
    workflow_id: str
    status: str  # success | failed
    action_results: list[ActionResult] = field(default_factory=list)


class WorkflowEngine:
    def __init__(
        self,
        store: ExecutionStore,
        action_executor: ActionExecutor | None = None,
        notification_service: NotificationService | None = None,
        catalog: dict[str, Workflow] | None = None,
        db=None,
    ):
        self._store = store
        self._executor = action_executor or ActionExecutor()
        self._notifications = notification_service or NotificationService()
        self._catalog = catalog or WORKFLOW_CATALOG
        self._db = db

    def run(self, workflow_id: str, event: CanonicalEvent) -> WorkflowRun:
        workflow = self._get_enabled_workflow(workflow_id)
        record: ExecutionRecord = self._store.start_execution(event, workflow_id)
        logger.info("WORKFLOW STARTED event_id=%s workflow_id=%s", event.event_id, workflow_id)
        return self._execute_steps(workflow, event, record)

    def retry(self, event_id: str) -> WorkflowRun | None:
        """Re-run a previously FAILED execution using its persisted event
        payload. Returns None if there's no execution for this event_id or
        it isn't currently in a failed (dead-letter) state -- retrying a
        success or an in-progress run is not this method's job."""
        fetched = self._store.get_event_for_retry(event_id)
        if fetched is None:
            return None
        record, event = fetched
        workflow = self._get_enabled_workflow(record.workflow_id)
        logger.info("WORKFLOW RETRY event_id=%s workflow_id=%s", event.event_id, record.workflow_id)
        return self._execute_steps(workflow, event, record)

    def _get_enabled_workflow(self, workflow_id: str) -> Workflow:
        workflow = self._catalog.get(workflow_id)
        if workflow is None or not workflow.enabled:
            raise ValueError(f"unknown or disabled workflow: {workflow_id}")
        return workflow

    def _execute_steps(self, workflow: Workflow, event: CanonicalEvent, record: ExecutionRecord) -> WorkflowRun:
        context: dict = {"notification_service": self._notifications, "db": self._db}
        action_results: list[ActionResult] = []
        run_status = "success"

        for step in sorted(workflow.steps, key=lambda s: s.order):
            result = self._executor.execute(step.action, event, context)
            action_results.append(result)
            self._store.record_action(record, step.action, result.status, result.attempts, result.error)

            if result.status == "success":
                logger.info(
                    "ACTION %d SUCCESS event_id=%s action=%s", step.order, event.event_id, step.action
                )
            else:
                logger.error(
                    "ACTION %d FAILED event_id=%s action=%s error=%s",
                    step.order, event.event_id, step.action, result.error,
                )
                run_status = "failed"
                # Stop the chain on first failure -- later actions (e.g.
                # record_execution) assume prior steps succeeded.
                break

        self._store.complete_execution(record, run_status, None if run_status == "success" else "one or more actions failed")
        logger.info("WORKFLOW %s event_id=%s workflow_id=%s", run_status.upper(), event.event_id, record.workflow_id)

        return WorkflowRun(
            event_id=event.event_id,
            workflow_id=workflow.workflow_id,
            status=run_status,
            action_results=action_results,
        )
