"""
Read-only Audit API (Stage 6, Part 9).

Exposes the audit trail written by AuditService (app/services/audit.py)
for querying/filtering. Nothing here writes -- audit records are only
ever created from the automation integration hooks in
app/automation/consumer.py and app/automation/workflows.py.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.audit import AuditRecordRead
from app.services.audit import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditRecordRead])
def list_audit_records(
    event_id: str | None = None,
    workflow_id: str | None = None,
    status: str | None = None,
    event_type: str | None = None,
    audit_type: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[AuditRecordRead]:
    service = AuditService(db)
    records = service.query(
        event_id=event_id,
        workflow_id=workflow_id,
        status=status,
        event_type=event_type,
        audit_type=audit_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    return [AuditRecordRead.from_model(r) for r in records]


@router.get("/event/{event_id}", response_model=list[AuditRecordRead])
def get_audit_by_event(event_id: str, db: Session = Depends(get_db)) -> list[AuditRecordRead]:
    """The primary trace endpoint: every audit record for one event_id,
    newest first -- answers 'what happened to event X?' (Part 2)."""
    service = AuditService(db)
    records = service.get_by_event(event_id)
    return [AuditRecordRead.from_model(r) for r in records]


@router.get("/workflow/{workflow_id}", response_model=list[AuditRecordRead])
def get_audit_by_workflow(workflow_id: str, db: Session = Depends(get_db)) -> list[AuditRecordRead]:
    service = AuditService(db)
    records = service.get_by_workflow(workflow_id)
    return [AuditRecordRead.from_model(r) for r in records]


@router.get("/{audit_id}", response_model=AuditRecordRead)
def get_audit_record(audit_id: uuid.UUID, db: Session = Depends(get_db)) -> AuditRecordRead:
    service = AuditService(db)
    record = service.get_by_id(audit_id)
    if record is None:
        raise HTTPException(status_code=404, detail="no audit record found for this audit_id")
    return AuditRecordRead.from_model(record)
