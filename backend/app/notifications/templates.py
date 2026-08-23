"""
Notification templates.

Pure functions: CanonicalEvent -> (subject, body). No provider, no I/O,
no side effects -- kept separate from providers.py so the wording of a
message and how it gets delivered never have to change together.

TEMPLATE_REGISTRY maps an event_type string (CanonicalEvent.event_type.value)
to the builder for that event, mirroring the ACTION_REGISTRY pattern already
used in app/automation/actions.py. actions.create_notification uses this
registry (see app/automation/actions.py) -- add a new event's template here,
not by editing actions.py.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from app.automation.events import CanonicalEvent

TemplateFn = Callable[["CanonicalEvent"], tuple[str, str]]


def build_attendance_warning_message(event: "CanonicalEvent") -> tuple[str, str]:
    """Low attendance warning. Pulls attendance percentage and subject
    straight from the event -- never hardcodes a particular student's
    details."""
    pct = event.data.get("attendance_percentage")
    subject_id = event.data.get("subject_id", "your course")
    subject = "Low Attendance Warning"
    body = (
        f"Your attendance in {subject_id} is {pct}%, which is below the "
        f"75% requirement. Please contact your department office."
    )
    return subject, body


def build_fee_confirmation_message(event: "CanonicalEvent") -> tuple[str, str]:
    """Fee payment confirmation. Amount/fee_type come from the event
    payload (i.e. whatever Person A's fee service reported), not from a
    fixed example."""
    amount = event.data.get("amount")
    fee_type = event.data.get("fee_type", "fee")
    subject = "Fee Payment Confirmation"
    body = f"We've received your {fee_type} payment of {amount}. Thank you."
    return subject, body


TEMPLATE_REGISTRY: dict[str, TemplateFn] = {
    "attendance.marked": build_attendance_warning_message,
    "fee.paid": build_fee_confirmation_message,
}
