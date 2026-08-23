from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.execution import ActionExecution, Execution


def list_all(db: Session, limit: int = 50) -> list[Execution]:
    return list(
        db.execute(
            select(Execution).order_by(Execution.started_at.desc()).limit(limit)
        ).scalars()
    )


def list_dead_letters(db: Session, limit: int = 50) -> list[Execution]:
    return list(
        db.execute(
            select(Execution)
            .where(Execution.status == "failed")
            .order_by(Execution.started_at.desc())
            .limit(limit)
        ).scalars()
    )


def get_by_event_id(db: Session, event_id: str) -> Execution | None:
    return db.execute(
        select(Execution).where(Execution.event_id == event_id)
    ).scalar_one_or_none()


def create_running(db: Session, event_id: str, workflow_id: str, event_payload: str) -> Execution:
    execution = Execution(
        event_id=event_id, workflow_id=workflow_id, status="running", event_payload=event_payload
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def reset_to_running(db: Session, execution: Execution) -> Execution:
    """Used by dead-letter retry: reuse the existing row (event_id is
    unique, so a fresh Execution can't be created for the same event)
    rather than losing the original started_at/history."""
    execution.status = "running"
    execution.completed_at = None
    execution.error = None
    db.commit()
    db.refresh(execution)
    return execution


def mark_completed(db: Session, execution: Execution, status: str, error: str | None = None) -> Execution:
    execution.status = status
    execution.completed_at = datetime.now(timezone.utc)
    execution.error = error
    db.commit()
    db.refresh(execution)
    return execution


def add_action_execution(
    db: Session,
    execution: Execution,
    action_type: str,
    status: str,
    attempt: int,
    error: str | None = None,
) -> ActionExecution:
    action_execution = ActionExecution(
        execution_id=execution.id,
        action_type=action_type,
        status=status,
        attempt=attempt,
        completed_at=datetime.now(timezone.utc),
        error=error,
    )
    db.add(action_execution)
    db.commit()
    db.refresh(action_execution)
    return action_execution
