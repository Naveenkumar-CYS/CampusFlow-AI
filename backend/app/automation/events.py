"""
Canonical Event Contract.

This is the ONLY event shape the automation engine (consumer, rule engine,
workflow engine) ever sees. Real producers (Person A's services, the dummy
producer) never talk to the engine directly — everything goes through this
envelope.

Deliberately NOT identical to EVENT_CONTRACT_PROPOSAL.md's draft (that one
is a producer-facing proposal for student/admission events aimed at
Person B; this one is the internal engine contract for automation events
like attendance/fees/hostel). They're allowed to diverge — reconciling
them is exactly what the ProducerAdapter (see adapter.py) is for.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventType(str, Enum):
    """
    Known internal event types. This is intentionally an allow-list, not a
    free string field — an unknown event_type should fail validation
    loudly rather than silently pass through to the rule engine.

    Add new types here as new workflows are built. Do NOT add a type until
    a rule actually consumes it.
    """

    ATTENDANCE_MARKED = "attendance.marked"
    FEE_PAID = "fee.paid"
    HOSTEL_ALLOCATED = "hostel.allocated"
    EXAM_REGISTERED = "exam.registered"


class CanonicalEvent(BaseModel):
    """
    The internal event envelope. `schema_version` is on the envelope
    itself (not just `data`) so the consumer can reject an envelope shape
    it doesn't understand before even looking at event_type.
    """

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    schema_version: str = "1.0"
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    aggregate_type: str
    aggregate_id: str
    student_id: str
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def _only_known_schema_version(cls, v: str) -> str:
        # Day-1 automation backbone only understands 1.0. Bump this
        # allow-list deliberately when a breaking payload change ships,
        # not by accident.
        if v != "1.0":
            raise ValueError(f"unsupported schema_version: {v!r}")
        return v


class EventValidationError(Exception):
    """Raised when a raw payload cannot be turned into a CanonicalEvent."""

    def __init__(self, message: str, raw: dict[str, Any] | None = None):
        super().__init__(message)
        self.raw = raw
