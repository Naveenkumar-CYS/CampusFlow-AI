"""
Producer Adapter -- the integration boundary for Person A.

    A's Service -> A's Event -> ProducerAdapter -> CanonicalEvent -> EventConsumer

PENDING A'S IMPLEMENTATION. Nothing below is a real mapping -- A hasn't
started yet, so there is no real payload to map from. This module exists
so the seam is visible and so wiring A's producer in later is "write one
adapter function + register it," not a rewrite of anything upstream.

--------------------------------------------------------------------
EXPECTED INPUT FROM A -- fill in once A's service exists:

    event type:      ?  (does A emit "attendance.marked" already, or
                          something else we need to rename here?)
    payload shape:    ?  (flat dict? nested? field names?)
    identifier:       ?  (does A use student_id the human-readable code,
                          or the internal UUID? EVENT_CONTRACT_PROPOSAL.md
                          says human-readable -- confirm this still holds
                          for attendance/fees/hostel too)
    timestamp:        ?  (field name, timezone, format)
    schema version:   ?  (does A version payloads at all?)
    transport:        ?  (direct function call, HTTP webhook, queue --
                          this file assumes "adapt() is called with a
                          dict," which works for any of them)
--------------------------------------------------------------------
"""
from __future__ import annotations

from typing import Any, Callable

from app.automation.events import CanonicalEvent

AdapterFn = Callable[[dict[str, Any]], CanonicalEvent]


class UnknownProducerEventError(Exception):
    pass


class ProducerAdapter:
    """Translates a producer-specific payload into a CanonicalEvent.

    Register one mapping function per producer event type once A defines
    them. Nothing is registered yet -- see the header of this file.
    """

    def __init__(self) -> None:
        self._mappings: dict[str, AdapterFn] = {}

    def register(self, producer_event_type: str, fn: AdapterFn) -> None:
        self._mappings[producer_event_type] = fn

    def adapt(self, raw_payload: dict[str, Any]) -> CanonicalEvent:
        producer_event_type = raw_payload.get("event_type") or raw_payload.get("type")
        fn = self._mappings.get(producer_event_type) if producer_event_type else None
        if fn is None:
            raise UnknownProducerEventError(
                f"no adapter registered for producer event type: {producer_event_type!r}"
            )
        return fn(raw_payload)
