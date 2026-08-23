"""
Rule Engine.

Deterministic, in-memory rule catalog. Deliberately NOT a general
expression language — each rule's `condition` is a plain Python callable
over the event's `data` dict. That's enough for "field < threshold"
style logic and keeps this auditable at a glance, which matters more than
flexibility on a hackathon timeline.

Separate from the Workflow Engine on purpose: a rule's only job is
"does this event match, and if so which workflow fires" — it does not
know how that workflow executes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.automation.events import CanonicalEvent, EventType

Condition = Callable[[dict], bool]


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    event_type: EventType
    condition: Condition
    workflow_id: str
    enabled: bool = True


def _attendance_below_75(data: dict) -> bool:
    return data.get("attendance_percentage", 100) < 75


def _fee_paid_always(data: dict) -> bool:
    return True


# The rule catalog. Order matters only in that the first enabled match
# wins — keep rules for the same event_type mutually exclusive where
# possible to avoid relying on ordering.
DEFAULT_RULES: list[Rule] = [
    Rule(
        id="RULE-001",
        name="Low attendance triggers warning",
        event_type=EventType.ATTENDANCE_MARKED,
        condition=_attendance_below_75,
        workflow_id="attendance_warning",
        enabled=True,
    ),
    Rule(
        id="RULE-002",
        name="Fee payment triggers confirmation",
        event_type=EventType.FEE_PAID,
        condition=_fee_paid_always,
        workflow_id="fee_payment_confirmation",
        enabled=True,
    ),
]


class RuleEngine:
    def __init__(self, rules: list[Rule] | None = None):
        self._rules = rules if rules is not None else list(DEFAULT_RULES)

    def match(self, event: CanonicalEvent) -> Rule | None:
        for rule in self._rules:
            if not rule.enabled:
                continue
            if rule.event_type != event.event_type:
                continue
            if rule.condition(event.data):
                return rule
        return None
