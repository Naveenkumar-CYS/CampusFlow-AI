"""
Stage 6 -- Audit / Traceability schemas.

``AuditType`` enumerates the automation lifecycle stages the audit
system records (Part 11 of the Stage 6 brief): an event being received,
a rule evaluation, an AI advisory call, a workflow run, an individual
action, and a notification send. ``AuditStatus`` is the small, fixed set
of execution outcomes an audit record can report (Part 4) -- kept
deliberately small rather than a large state machine.

Both are plain ``str`` enums (same pattern as
``app.automation.events.EventType``) so they serialize as plain strings
over the API and compare cleanly against the ``String`` columns on
``app.models.audit.AuditRecord``.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class AuditType(str, Enum):
    EVENT_PROCESSED = "EVENT_PROCESSED"
    RULE_EVALUATED = "RULE_EVALUATED"
    AI_ADVISORY = "AI_ADVISORY"
    WORKFLOW_EXECUTED = "WORKFLOW_EXECUTED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    NOTIFICATION_EXECUTED = "NOTIFICATION_EXECUTED"


class AuditStatus(str, Enum):
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    RETRYING = "RETRYING"


class AuditRecordRead(BaseModel):
    """Read-only API representation of one audit record.

    Deliberately flat (no nested objects) -- ``context`` is the one place
    small structured extras (AI metadata, a matched rule id, a skip
    reason, ...) live, per Part 8's "a JSON metadata field is acceptable
    for small structured information".
    """

    model_config = ConfigDict(from_attributes=False)

    audit_id: uuid.UUID
    audit_type: str
    status: str
    component: str
    event_id: str | None = None
    workflow_id: str | None = None
    execution_id: uuid.UUID | None = None
    action: str | None = None
    event_type: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    context: dict | None = None
    created_at: datetime

    @classmethod
    def from_model(cls, record) -> "AuditRecordRead":
        return cls(
            audit_id=record.id,
            audit_type=record.audit_type,
            status=record.status,
            component=record.component,
            event_id=record.event_id,
            workflow_id=record.workflow_id,
            execution_id=record.execution_id,
            action=record.action,
            event_type=record.event_type,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            error_type=record.error_type,
            error_message=record.error_message,
            context=record.context,
            created_at=record.created_at,
        )
