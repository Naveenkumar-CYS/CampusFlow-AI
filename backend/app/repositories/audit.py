import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditRecord


def create(db: Session, **fields) -> AuditRecord:
    record = AuditRecord(**fields)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_by_id(db: Session, audit_id: uuid.UUID) -> AuditRecord | None:
    return db.get(AuditRecord, audit_id)


def query(
    db: Session,
    *,
    event_id: str | None = None,
    workflow_id: str | None = None,
    status: str | None = None,
    event_type: str | None = None,
    audit_type: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 50,
) -> list[AuditRecord]:
    """Filtered, newest-first query over automation_audit_records.

    Every filter is optional and additive (AND'd together) -- omitted
    filters simply aren't applied. Used directly by AuditService.query()
    / get_by_event() / get_by_workflow() (see app/services/audit.py) and,
    through those, by the read-only audit API (app/api/audit.py).
    """
    stmt = select(AuditRecord)

    if event_id is not None:
        stmt = stmt.where(AuditRecord.event_id == event_id)
    if workflow_id is not None:
        stmt = stmt.where(AuditRecord.workflow_id == workflow_id)
    if status is not None:
        stmt = stmt.where(AuditRecord.status == status)
    if event_type is not None:
        stmt = stmt.where(AuditRecord.event_type == event_type)
    if audit_type is not None:
        stmt = stmt.where(AuditRecord.audit_type == audit_type)
    if start_time is not None:
        stmt = stmt.where(AuditRecord.created_at >= start_time)
    if end_time is not None:
        stmt = stmt.where(AuditRecord.created_at <= end_time)

    stmt = stmt.order_by(AuditRecord.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars())
