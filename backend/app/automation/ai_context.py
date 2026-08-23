"""
AI Advisory integration adapter (Stage 5B-2).

    CanonicalEvent (attendance.marked)
              |
              v
    for_event() -- maps existing event fields onto the existing
                   Stage 5B-1 input shape (StudentRiskFeaturesInput +
                   attendance_history)
              |
              v
    app.analytics.advisory.get_ai_advisory()   <- EXISTING Stage 5B-1
                                                    AI Advisory Service,
                                                    called exactly as-is
              |
              v
    AIAdvisoryResult | None

This is the ONLY new code Stage 5B-2 adds between the automation layer
and the analytics layer. It does not:
    - train or load a model directly (that stays in app.analytics.risk)
    - duplicate prediction or attendance-pattern logic
    - create a second AI service / classifier
    - invent a new event contract or attendance event type

It reuses the exact fields already present on CanonicalEvent.data (see
app/automation/events.py, app/automation/producer.py) -- nothing here
requires Person A (or the dummy producer) to change their payload
shape. Fields the input schema wants but the event doesn't carry
(average_marks, missed_assignments, fee_overdue_indicator,
attendance_history) are simply left as None/absent; the existing
StudentRiskFeaturesInput / analyze_attendance() already define neutral
defaults and INSUFFICIENT_DATA handling for exactly that case -- this
adapter does not reimplement or work around that.

Only ATTENDANCE_MARKED events carry the academic-risk signal the AI
Advisory Service is scoped to (see CampusFlow_AI_Architecture.md:
"Rule Engine evaluates threshold -> if breached, AI Analytics scores
risk level"). Other event types (fee.paid, hostel.allocated,
exam.registered) have nothing for it to advise on yet, so for_event()
returns None for them rather than calling the model with meaningless
imputed defaults -- this is what keeps the AI an *advisory add-on* to
the attendance flow instead of a second rule engine over unrelated
events.
"""
from __future__ import annotations

import logging

from pydantic import ValidationError

from app.analytics.advisory import get_ai_advisory
from app.analytics.schemas import AIAdvisoryResult, StudentRiskFeaturesInput
from app.automation.events import CanonicalEvent, EventType

logger = logging.getLogger("campusflow.automation.ai_context")

# Keys read from CanonicalEvent.data. These are additive/optional on
# top of the existing attendance.marked payload (attendance_percentage
# already exists -- see producer.py; the rest are opportunistic: if a
# future producer/event ever includes them under these names they are
# picked up automatically, and if not, they're simply absent and the
# existing imputation in app.analytics.features handles it).
_FEATURE_KEYS = ("attendance_percentage", "average_marks", "missed_assignments", "fee_overdue_indicator")


def for_event(event: CanonicalEvent) -> AIAdvisoryResult | None:
    """
    Return the Stage 5B-1 AI Advisory Service's result for this event,
    or None if this event type isn't one the AI Advisory Service is
    scoped to advise on.

    Never raises: this sits on the deterministic automation path, and a
    mapping problem here must degrade to "no AI advisory this run" (see
    Part 10 of the Stage 5B-2 brief), not break the workflow. The
    underlying get_ai_advisory() call already never raises for
    "expected" ML/attendance failure modes (see advisory.py) -- the
    try/except here only guards the adapter's own mapping step.
    """
    if event.event_type != EventType.ATTENDANCE_MARKED:
        return None

    data = event.data
    try:
        features = StudentRiskFeaturesInput(**{k: data.get(k) for k in _FEATURE_KEYS})
    except ValidationError as exc:
        logger.warning(
            "event_id=%s attendance payload could not be mapped to AI "
            "advisory features; skipping AI advisory for this run: %s",
            event.event_id, exc,
        )
        return None

    attendance_history = data.get("attendance_history")
    if attendance_history is None and data.get("attendance_percentage") is not None:
        # No explicit history on the event -- fall back to a single
        # current-value observation so the attendance analyzer at least
        # reflects the current reading. A one-point history is still
        # honestly reported as INSUFFICIENT_DATA by analyze_attendance()
        # for anything trend-based; this adapter does not fabricate a
        # longer history to force a pattern classification.
        attendance_history = [data.get("attendance_percentage")]

    try:
        return get_ai_advisory(features, attendance_history=attendance_history)
    except Exception:  # noqa: BLE001 -- the AI advisory path must never
        # take down the deterministic workflow; get_ai_advisory() already
        # catches its own expected failure modes internally, so anything
        # reaching here is unexpected and is logged, not propagated.
        logger.exception(
            "event_id=%s unexpected error calling AI Advisory Service; "
            "continuing workflow without AI advisory for this run",
            event.event_id,
        )
        return None
