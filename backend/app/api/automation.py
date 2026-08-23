"""
Debug/manual-trigger endpoints for the automation backbone.

These stand in for a real transport (queue/webhook) receiving events from
Person A's producer once it exists. Until then, this is how the chain
gets exercised: manually, via HTTP, using the dummy producer.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.automation.consumer import EventConsumer
from app.automation.producer import make_attendance_marked_event, make_fee_paid_event
from app.automation.rules import RuleEngine
from app.automation.store import DbExecutionStore
from app.automation.workflows import WorkflowEngine
from app.db.session import get_db
from app.repositories import execution as execution_repo
from app.schemas.automation import (
    ActionResultRead,
    TriggerAttendanceMarkedRequest,
    TriggerEventResponse,
    TriggerFeePaidRequest,
)
from app.services.audit import AuditService

router = APIRouter(prefix="/automation", tags=["automation"])


def _run_consumer(db: Session, event) -> TriggerEventResponse:
    store = DbExecutionStore(db)
    audit = AuditService(db)
    workflow_engine = WorkflowEngine(store, db=db, audit_service=audit)
    consumer = EventConsumer(RuleEngine(), workflow_engine, store, audit_service=audit)
    result = consumer.consume(event)

    return TriggerEventResponse(
        event_id=result.event.event_id,
        event_type=result.event.event_type.value,
        status=result.status,
        workflow_id=result.workflow_run.workflow_id if result.workflow_run else None,
        workflow_status=result.workflow_run.status if result.workflow_run else None,
        actions=[
            ActionResultRead(action=a.action, status=a.status, attempts=a.attempts, error=a.error)
            for a in (result.workflow_run.action_results if result.workflow_run else [])
        ],
    )


@router.post("/dummy-events/attendance-marked", response_model=TriggerEventResponse)
def trigger_attendance_marked(
    payload: TriggerAttendanceMarkedRequest, db: Session = Depends(get_db)
) -> TriggerEventResponse:
    event = make_attendance_marked_event(
        student_id=payload.student_id,
        subject_id=payload.subject_id,
        attendance_percentage=payload.attendance_percentage,
        status=payload.status,
    )
    if payload.contact_email:
        event.data["contact_email"] = payload.contact_email
    if payload.contact_phone:
        event.data["contact_phone"] = payload.contact_phone
    return _run_consumer(db, event)


@router.post("/dummy-events/fee-paid", response_model=TriggerEventResponse)
def trigger_fee_paid(
    payload: TriggerFeePaidRequest, db: Session = Depends(get_db)
) -> TriggerEventResponse:
    event = make_fee_paid_event(
        student_id=payload.student_id, amount=payload.amount, fee_type=payload.fee_type
    )
    if payload.contact_email:
        event.data["contact_email"] = payload.contact_email
    return _run_consumer(db, event)


@router.get("/executions")
def list_executions(limit: int = 50, db: Session = Depends(get_db)):
    executions = execution_repo.list_all(db, limit=limit)
    return [
        {
            "event_id": e.event_id,
            "workflow_id": e.workflow_id,
            "status": e.status,
            "started_at": e.started_at,
            "completed_at": e.completed_at,
        }
        for e in executions
    ]


@router.get("/executions/dead-letters")
def list_dead_letters(limit: int = 50, db: Session = Depends(get_db)):
    """Failed executions that stopped after exhausting action retries.
    Nothing here requeues automatically -- see POST .../retry."""
    executions = execution_repo.list_dead_letters(db, limit=limit)
    return [
        {
            "event_id": e.event_id,
            "workflow_id": e.workflow_id,
            "started_at": e.started_at,
            "completed_at": e.completed_at,
            "error": e.error,
        }
        for e in executions
    ]


@router.post("/executions/{event_id}/retry", response_model=TriggerEventResponse)
def retry_dead_letter(event_id: str, db: Session = Depends(get_db)) -> TriggerEventResponse:
    store = DbExecutionStore(db)
    engine = WorkflowEngine(store, db=db, audit_service=AuditService(db))
    run = engine.retry(event_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail="no failed execution found for this event_id (already succeeded, still running, or never existed)",
        )
    return TriggerEventResponse(
        event_id=run.event_id,
        event_type="",  # not reconstructed here; see /executions/{event_id} for the full trace
        status="workflow_triggered",
        workflow_id=run.workflow_id,
        workflow_status=run.status,
        actions=[
            ActionResultRead(action=a.action, status=a.status, attempts=a.attempts, error=a.error)
            for a in run.action_results
        ],
    )


@router.get("/executions/{event_id}")
def get_execution_trace(event_id: str, db: Session = Depends(get_db)):
    execution = execution_repo.get_by_event_id(db, event_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="no execution found for this event_id")
    return {
        "event_id": execution.event_id,
        "workflow_id": execution.workflow_id,
        "status": execution.status,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "error": execution.error,
        "actions": [
            {
                "action_type": a.action_type,
                "status": a.status,
                "attempt": a.attempt,
                "error": a.error,
            }
            for a in execution.action_executions
        ],
    }
