import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# AuditRecord.execution_id below is a string ForeignKey to
# "automation_executions" (owned by app.models.execution). Import that
# module here -- not just in app/models/__init__.py -- so that
# `from app.models.audit import AuditRecord` alone (without first
# importing app.models.execution) still leaves Base.metadata with both
# tables registered before any flush tries to resolve the FK. See
# app/models/__init__.py for the fuller explanation.
from app.models import execution as _execution  # noqa: F401


class AuditRecord(Base):
    """One row per meaningful automation lifecycle event (Stage 6).

    Complements, rather than replaces, the existing ``Execution`` /
    ``ActionExecution`` tables (see app/models/execution.py): those are
    frozen Stage 3/4 tables keyed one row per *workflow run* / *action
    attempt*, and ``Execution.event_id`` is unique -- neither can
    represent an event that never triggered a workflow at all (no rule
    matched, a duplicate was skipped) or a lifecycle stage like rule
    evaluation or an AI advisory call. AuditRecord is deliberately
    append-only and unconstrained on event_id/workflow_id so it can hold
    one row per lifecycle stage per execution, including stages that
    never reach the Execution table.

    ``event_id`` / ``workflow_id`` / ``execution_id`` are the existing
    identifiers used elsewhere in the automation stack (Part 2 --
    traceability reuses these rather than inventing a parallel identity
    system). ``execution_id`` links back to the specific
    ``automation_executions`` row when one exists for this event.
    """

    __tablename__ = "automation_audit_records"
    __table_args__ = (
        Index("ix_audit_records_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # What lifecycle stage this record describes -- one of
    # app.schemas.audit.AuditType (EVENT_PROCESSED, RULE_EVALUATED,
    # AI_ADVISORY, WORKFLOW_EXECUTED, ACTION_EXECUTED,
    # NOTIFICATION_EXECUTED). Plain String, not a DB enum type, so a new
    # audit type never requires a migration -- validated at the
    # AuditService boundary instead (see app/services/audit.py).
    audit_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # STARTED | SUCCESS | FAILED | SKIPPED | RETRYING -- see AuditStatus.
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Which component produced this record, e.g. "event_consumer",
    # "rule_engine", "ai_advisory", "workflow_engine", "action_executor",
    # "notification_service".
    component: Mapped[str] = mapped_column(String(50), nullable=False)

    # Traceability identifiers (Part 2). All nullable -- not every
    # lifecycle stage has every identifier available (e.g. RULE_EVALUATED
    # for a no-match has no workflow_id).
    event_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    workflow_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("automation_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Action name (e.g. "send_email") for ACTION_EXECUTED /
    # NOTIFICATION_EXECUTED, or a matched rule id for RULE_EVALUATED.
    action: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # CanonicalEvent.event_type.value, e.g. "attendance.marked".
    event_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # CanonicalEvent.aggregate_type / aggregate_id -- reused as-is
    # (Part 1: "do not invent identifiers that cannot actually be
    # populated"). Deliberately NOT student_id: the audit trail traces
    # *executions*, not students, and aggregate_id is already the
    # existing identifier for that (see app/automation/events.py).
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Error information (Part 5). error_message is sanitized by
    # AuditService before it ever reaches this column -- see
    # app/services/audit.py's _sanitize().
    error_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Small structured extras only (Part 8) -- e.g. AI advisory metadata
    # (model_version/risk_level/risk_score/attendance_pattern) or a skip
    # reason. Never the full model, training data, or raw student PII.
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
