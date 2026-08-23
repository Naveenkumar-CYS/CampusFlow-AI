"""
Workflow Engine.

Orchestrates an ordered list of actions. Does NOT implement email/SMS
itself -- that's actions.py's job via NotificationService. Wraps the run
in the ExecutionStore so every run is traceable by event_id (Step 13) and
so a duplicate event_id never re-runs a workflow (Step 11).

Stage 5B-2: also computes the (optional) AI Advisory Service result for
the event once per run and places it in the shared action context under
"ai_advisory" -- see ai_context.py. This is advisory metadata only; the
Workflow Engine's own step-sequencing/failure semantics are unchanged,
and a missing/failed AI result never blocks or fails a workflow run.

Stage 6: an optional `audit_service` records AI_ADVISORY, ACTION_EXECUTED
/ NOTIFICATION_EXECUTED, and WORKFLOW_EXECUTED audit entries (see
app/services/audit.py). Additive only -- defaults to None, and
AuditService.record() never raises, so this can't change a WorkflowRun's
status/action_results or block a run.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.automation import ai_context
from app.automation.actions import ActionExecutor, ActionResult
from app.automation.events import CanonicalEvent
from app.automation.notifications import NotificationService
from app.automation.store import ExecutionRecord, ExecutionStore
from app.schemas.audit import AuditStatus, AuditType

logger = logging.getLogger("campusflow.automation.workflow")

# Actions that represent an outbound notification, for the
# ACTION_EXECUTED vs. NOTIFICATION_EXECUTED audit-type distinction
# (Part 11). Everything else in the action catalog audits as
# ACTION_EXECUTED.
_NOTIFICATION_ACTIONS = frozenset({"send_email", "send_sms"})


def _execution_pk(record: ExecutionRecord):
    """The DB primary key of this run's Execution row, if the store
    backing this run is DB-backed (see automation/store.py's
    DbExecutionStore, which stashes it as record._db_execution) --
    otherwise None. Lets audit records reference the specific
    automation_executions row without the Workflow Engine needing to
    know which ExecutionStore implementation it's running against."""
    db_execution = getattr(record, "_db_execution", None)
    return db_execution.id if db_execution is not None else None


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
    "hostel_allocation_confirmation": Workflow(
        workflow_id="hostel_allocation_confirmation",
        name="Hostel Allocation Confirmation",
        steps=[
            WorkflowStep(1, "create_notification"),
            WorkflowStep(2, "send_email"),
            WorkflowStep(3, "record_execution"),
        ],
    ),
    "exam_registration_confirmation": Workflow(
        workflow_id="exam_registration_confirmation",
        name="Exam Registration Confirmation",
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
        audit_service: Any | None = None,
    ):
        self._store = store
        self._executor = action_executor or ActionExecutor()
        self._notifications = notification_service or NotificationService()
        self._catalog = catalog or WORKFLOW_CATALOG
        self._db = db
        self._audit = audit_service

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
        # Rule match -> AI advisory result (Stage 5B-2): computed once per
        # workflow run and handed to every action via the existing shared
        # context dict, the same mechanism create_notification already
        # uses to pass subject/body to send_email/send_sms. ai_context
        # returns None for event types the AI Advisory Service isn't
        # scoped to (see ai_context.py) and never raises, so this can't
        # turn a deterministic workflow failure into an AI failure or
        # vice versa -- the AI result is purely additive context.
        context: dict = {
            "notification_service": self._notifications,
            "db": self._db,
            "ai_advisory": ai_context.for_event(event),
        }

        if self._audit is not None:
            self._record_ai_advisory_audit(event, workflow.workflow_id, record, context["ai_advisory"])

        action_results: list[ActionResult] = []
        run_status = "success"

        for step in sorted(workflow.steps, key=lambda s: s.order):
            result = self._executor.execute(step.action, event, context)
            action_results.append(result)
            self._store.record_action(record, step.action, result.status, result.attempts, result.error)

            if self._audit is not None:
                self._record_step_audit(event, workflow.workflow_id, record, step, result)

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

        if self._audit is not None:
            self._audit.record(
                audit_type=AuditType.WORKFLOW_EXECUTED,
                status=AuditStatus.SUCCESS if run_status == "success" else AuditStatus.FAILED,
                component="workflow_engine",
                event_id=event.event_id,
                workflow_id=workflow.workflow_id,
                execution_id=_execution_pk(record),
                event_type=event.event_type.value,
                entity_type=event.aggregate_type,
                entity_id=event.aggregate_id,
                error_type="workflow_failed" if run_status != "success" else None,
                error_message="one or more actions failed" if run_status != "success" else None,
            )

        return WorkflowRun(
            event_id=event.event_id,
            workflow_id=workflow.workflow_id,
            status=run_status,
            action_results=action_results,
        )

    def _record_ai_advisory_audit(self, event, workflow_id, record, advisory) -> None:
        if advisory is None:
            return
        self._audit.record(
            audit_type=AuditType.AI_ADVISORY,
            status=AuditStatus.SUCCESS if advisory.ai_available else AuditStatus.FAILED,
            component="ai_advisory",
            event_id=event.event_id,
            workflow_id=workflow_id,
            execution_id=_execution_pk(record),
            event_type=event.event_type.value,
            entity_type=event.aggregate_type,
            entity_id=event.aggregate_id,
            error_type="ai_unavailable" if not advisory.ai_available else None,
            error_message=advisory.error,
            # Small, structured, advisory-only metadata (Part 3/15) --
            # never the model, training data, or raw student PII.
            context={
                "model_version": advisory.model_version,
                "risk_level": advisory.risk_level,
                "risk_score": advisory.risk_score,
                "attendance_pattern": advisory.attendance_pattern,
            },
        )

    def _record_step_audit(self, event, workflow_id, record, step, result: ActionResult) -> None:
        audit_type = (
            AuditType.NOTIFICATION_EXECUTED if step.action in _NOTIFICATION_ACTIONS else AuditType.ACTION_EXECUTED
        )
        self._audit.record(
            audit_type=audit_type,
            status=AuditStatus.SUCCESS if result.status == "success" else AuditStatus.FAILED,
            component="notification_service" if step.action in _NOTIFICATION_ACTIONS else "action_executor",
            event_id=event.event_id,
            workflow_id=workflow_id,
            execution_id=_execution_pk(record),
            action=step.action,
            event_type=event.event_type.value,
            entity_type=event.aggregate_type,
            entity_id=event.aggregate_id,
            error_type="action_failed" if result.status != "success" else None,
            error_message=result.error,
            context={"attempts": result.attempts},
        )
