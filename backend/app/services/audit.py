"""
Audit Service (Stage 6).

Centralizes every write to the audit trail (app/models/audit.py) so no
other module performs raw INSERTs against automation_audit_records --
Part 6 of the Stage 6 brief. Callers (EventConsumer, WorkflowEngine, the
audit API) only ever go through record() / query() / get_by_event() /
get_by_workflow() / get_by_id() below.

Failure isolation (Part 13): record() never raises. A failed audit write
is logged and swallowed -- the automation pipeline this sits alongside
must keep running even if the audit database is temporarily unavailable.
This is the ONE place that guarantee is implemented; callers in
app/automation/ don't need their own try/except around an audit call.

Secret/PII sanitization (Part 10, Part 3): error_message is passed
through _sanitize() before it ever reaches the database. Callers are
still responsible for not handing this service raw student PII or
secrets in the first place (see integration call sites in
app/automation/consumer.py and app/automation/workflows.py) -- this is a
best-effort net over exception text, not a substitute for that.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.audit import AuditRecord
from app.repositories import audit as audit_repo
from app.schemas.audit import AuditStatus, AuditType

logger = logging.getLogger("campusflow.services.audit")

_MAX_ERROR_LEN = 2000

# Best-effort redaction of "key: value" / "key=value" pairs whose key
# looks credential-like, wherever they appear in an error string (e.g.
# a raw provider exception that happened to include a config value).
# Deliberately conservative/broad rather than clever -- over-redacting a
# false positive is a much smaller problem than leaking a real secret.
#
# The key may be immediately followed by a closing quote before the
# delimiter (JSON-style `"api_key": "..."` ), and the value itself may
# be a quoted string, a `Bearer <token>` pair (HTTP Authorization
# headers put the actual secret in a second, space-separated word that
# a plain `\S+` value would miss), or a single unquoted token.
_SECRET_KEY_PATTERN = re.compile(
    r"(?i)\b(password|passwd|api[_-]?key|secret|token|smtp[_-]?password|"
    r"sms[_-]?api[_-]?key|authorization|access[_-]?token|session[_-]?token)\b"
    r"\"?\s*[:=]\s*"
    r"(\"[^\"]*\"|'[^']*'|Bearer\s+\S+|\S+)"
)


def _sanitize(message: str | None) -> str | None:
    """Redact credential-shaped substrings and cap length. Never raises;
    a message that fails to sanitize cleanly is dropped entirely rather
    than stored unredacted."""
    if message is None:
        return None
    try:
        redacted = _SECRET_KEY_PATTERN.sub(lambda m: f"{m.group(1)}=[REDACTED]", message)
    except Exception:  # noqa: BLE001 -- sanitization itself must never leak the original
        return "[error message could not be sanitized]"
    if len(redacted) > _MAX_ERROR_LEN:
        redacted = redacted[:_MAX_ERROR_LEN] + "...[truncated]"
    return redacted


class AuditService:
    """Thin, DB-session-bound wrapper around app.repositories.audit."""

    def __init__(self, db: Session):
        self._db = db

    def record(
        self,
        *,
        audit_type: AuditType | str,
        status: AuditStatus | str,
        component: str,
        event_id: str | None = None,
        workflow_id: str | None = None,
        execution_id: uuid.UUID | None = None,
        action: str | None = None,
        event_type: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        context: dict | None = None,
    ) -> AuditRecord | None:
        """Persist one audit record describing a single automation
        lifecycle stage. Returns the persisted row, or None if the write
        failed -- callers must not depend on this succeeding (Part 13)."""
        try:
            audit_type_value = audit_type.value if isinstance(audit_type, AuditType) else str(audit_type)
            status_value = status.value if isinstance(status, AuditStatus) else str(status)
            return audit_repo.create(
                self._db,
                audit_type=audit_type_value,
                status=status_value,
                component=component,
                event_id=event_id,
                workflow_id=workflow_id,
                execution_id=execution_id,
                action=action,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                error_type=error_type,
                error_message=_sanitize(error_message),
                context=context,
            )
        except Exception:  # noqa: BLE001 -- audit must never break automation (Part 13)
            logger.exception(
                "failed to persist audit record: type=%s component=%s event_id=%s workflow_id=%s",
                audit_type, component, event_id, workflow_id,
            )
            try:
                self._db.rollback()
            except Exception:  # noqa: BLE001 -- rollback failing is not this method's problem either
                pass
            return None

    def get_by_id(self, audit_id: uuid.UUID) -> AuditRecord | None:
        return audit_repo.get_by_id(self._db, audit_id)

    def get_by_event(self, event_id: str, limit: int = 100) -> list[AuditRecord]:
        """All audit records for one event_id, newest first -- the
        primary trace query (Part 2): 'what happened to event X?'."""
        return audit_repo.query(self._db, event_id=event_id, limit=limit)

    def get_by_workflow(self, workflow_id: str, limit: int = 100) -> list[AuditRecord]:
        return audit_repo.query(self._db, workflow_id=workflow_id, limit=limit)

    def query(
        self,
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
        return audit_repo.query(
            self._db,
            event_id=event_id,
            workflow_id=workflow_id,
            status=status,
            event_type=event_type,
            audit_type=audit_type,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
