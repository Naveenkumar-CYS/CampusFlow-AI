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

Multiple rules can legitimately target the same event_type (e.g. two
attendance thresholds at different severities). `priority` makes the
choice between them deterministic instead of relying on catalog order;
see RuleEngine.match/match_all below.
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
    # Higher priority is evaluated first when more than one rule could
    # match the same event_type. Rules with equal priority keep the order
    # they appear in the catalog (stable sort), so matching stays
    # deterministic either way -- no rule ever "wins" by accident.
    priority: int = 0


def _attendance_below_75(data: dict) -> bool:
    return data.get("attendance_percentage", 100) < 75


def _fee_paid_always(data: dict) -> bool:
    return True


# The rule catalog. Matching is by (priority desc, catalog order) --
# these two rules don't overlap in event_type today so ordering/priority
# is moot between them, but keep rules for the same event_type mutually
# exclusive where possible, and set an explicit priority instead of
# relying on position if they ever do overlap.
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
        """Return the single highest-priority enabled rule whose
        event_type and condition match this event, or None.

        When several rules could match the same event, priority decides
        which one wins; ties keep catalog order (stable sort) so the
        result never depends on incidental list ordering.
        """
        candidates = self.match_all(event)
        return candidates[0] if candidates else None

    def match_all(self, event: CanonicalEvent) -> list[Rule]:
        """Return every enabled rule matching this event, highest
        priority first (stable for equal priority). Useful for tests and
        introspection; the Event Processor only ever acts on match()'s
        top result -- selecting/executing more than one workflow per
        event is a later-stage concern, not this engine's job."""
        applicable = [
            rule
            for rule in self._rules
            if rule.enabled
            and rule.event_type == event.event_type
            and rule.condition(event.data)
        ]
        return sorted(applicable, key=lambda r: r.priority, reverse=True)
