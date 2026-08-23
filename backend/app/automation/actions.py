"""
Action Executor.

Actions are independently testable, small, and dumb: given the event plus
a shared mutable `context` dict (so e.g. create_notification can hand
send_email the subject/body it built), do one thing and return an
ActionResult. The executor wraps each call with a small configurable
retry -- it does not know or care what the action does.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from app.automation.events import CanonicalEvent
from app.automation.notifications import NotificationService
from app.notifications.templates import TEMPLATE_REGISTRY as _MESSAGE_BUILDERS

logger = logging.getLogger("campusflow.automation.actions")

DEFAULT_MAX_ATTEMPTS = 3


@dataclass
class ActionResult:
    action: str
    status: str  # "success" | "failed"
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    attempts: int = 1


ActionFn = Callable[[CanonicalEvent, dict], dict]


def _append_ai_advisory_note(body: str, context: dict) -> str:
    """Append a clearly-labelled advisory line to the notification body
    when an AI advisory result is available on the context (Stage 5B-2).

    Smallest possible context/template change per Part 8 of the Stage
    5B-2 brief: the template builders in app.notifications.templates are
    untouched (they still only see the event); this action is the one
    place that already assembles the final body, so it's the natural
    place to fold in advisory context that came from the workflow's
    shared `context` dict (the same mechanism used to hand send_email
    the subject/body this function builds).

    Deliberately advisory-only phrasing ("for staff review", never a
    decision/action verb) and clearly labelled as such -- never claims
    an intervention has happened. When AI is unavailable, says so
    plainly rather than fabricating or omitting that fact silently.
    """
    advisory = context.get("ai_advisory")
    if advisory is None:
        return body

    if not advisory.ai_available:
        return f"{body}\n\n[Advisory only -- AI risk assessment unavailable for this run.]"

    return (
        f"{body}\n\n[Advisory only, for staff review -- not an automatic decision] "
        f"AI risk assessment: {advisory.risk_level} "
        f"(attendance pattern: {advisory.attendance_pattern}). {advisory.advisory_message}"
    )


def create_notification(event: CanonicalEvent, context: dict) -> dict:
    builder = _MESSAGE_BUILDERS.get(event.event_type.value)
    if builder is None:
        raise ValueError(f"no message builder registered for {event.event_type.value}")
    subject, body = builder(event)
    body = _append_ai_advisory_note(body, context)
    context["notification"] = {"subject": subject, "body": body}
    return {"subject": subject}


def _resolve_student_contact(event: CanonicalEvent, context: dict) -> tuple[str, str]:
    """Resolve (email, phone) for the student this event is about.

    Priority: explicit override in event.data (used by the dummy producer
    and tests) -> DB lookup via context["db"] (the real path once a
    session is available) -> a fixed placeholder so actions never crash
    for lack of contact info -- a missing contact detail should show up
    as an obviously-fake placeholder in a mock log, not an exception.
    """
    email = event.data.get("contact_email")
    phone = event.data.get("contact_phone")

    if (email is None or phone is None) and context.get("db") is not None:
        from app.repositories import student as student_repo

        student = student_repo.get_by_student_id(context["db"], event.student_id)
        if student is not None:
            email = email or student.email
            phone = phone or student.phone

    return email or f"{event.student_id}@example.edu", phone or "+91-0000000000"


def send_email(event: CanonicalEvent, context: dict) -> dict:
    notification = context.get("notification")
    if notification is None:
        raise RuntimeError("send_email requires create_notification to run first")
    service: NotificationService = context["notification_service"]
    to, _ = _resolve_student_contact(event, context)
    result = service.send_email(to=to, subject=notification["subject"], body=notification["body"])
    if result.status != "sent":
        # Provider failure -> raise so the existing ActionExecutor retry /
        # dead-letter machinery (Stage 3) handles it, same as any other
        # action failure. The Notification Service never decides
        # retry/workflow behavior itself.
        raise RuntimeError(f"email provider failed: {result.error or 'unknown error'}")
    return {
        "to": to,
        "provider": result.provider,
        "provider_message_id": result.provider_message_id,
        "status": result.status,
    }


def send_sms(event: CanonicalEvent, context: dict) -> dict:
    notification = context.get("notification")
    if notification is None:
        raise RuntimeError("send_sms requires create_notification to run first")
    service: NotificationService = context["notification_service"]
    _, to = _resolve_student_contact(event, context)
    result = service.send_sms(to=to, body=notification["body"])
    if result.status != "sent":
        raise RuntimeError(f"sms provider failed: {result.error or 'unknown error'}")
    return {
        "to": to,
        "provider": result.provider,
        "provider_message_id": result.provider_message_id,
        "status": result.status,
    }


def record_execution(event: CanonicalEvent, context: dict) -> dict:
    # The execution store already persists a run record around the whole
    # workflow (see workflows.py) -- this action exists as an explicit,
    # visible step in the catalog per the spec, and is a natural place to
    # attach a final summary if one is ever needed.
    return {"event_id": event.event_id}


ACTION_REGISTRY: dict[str, ActionFn] = {
    "create_notification": create_notification,
    "send_email": send_email,
    "send_sms": send_sms,
    "record_execution": record_execution,
}


class ActionExecutor:
    def __init__(self, max_attempts: int = DEFAULT_MAX_ATTEMPTS, registry: dict[str, ActionFn] | None = None):
        self._max_attempts = max_attempts
        self._registry = registry or ACTION_REGISTRY

    def execute(self, action_name: str, event: CanonicalEvent, context: dict) -> ActionResult:
        fn = self._registry.get(action_name)
        if fn is None:
            return ActionResult(action=action_name, status="failed", error=f"unknown action: {action_name}")

        last_error: str | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                result = fn(event, context)
                return ActionResult(action=action_name, status="success", result=result, attempts=attempt)
            except Exception as exc:  # noqa: BLE001 -- action failures are data, not bugs
                last_error = str(exc)
                logger.warning(
                    "action %s failed on attempt %d/%d: %s",
                    action_name, attempt, self._max_attempts, last_error,
                )

        return ActionResult(action=action_name, status="failed", error=last_error, attempts=self._max_attempts)
