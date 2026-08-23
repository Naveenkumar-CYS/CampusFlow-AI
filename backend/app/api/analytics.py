"""
Optional demonstration endpoint for the AI Advisory Service (Stage 5B-1,
Part 6).

This exists only to demonstrate ``app.analytics.advisory.get_ai_advisory``
over HTTP; it is not required by, and does not participate in, the
automation pipeline (Redis / Event Processor / Rule Engine / Workflow
Engine / Action Executor -- that wiring is Stage 5B-2). Unlike the other
routers, this one has no database dependency, matching
``app.analytics``'s existing no-DB, no-event-bus design (see
``app/analytics/__init__.py``).

The result is always advisory-only (``AIAdvisoryResult.is_advisory_only``
is fixed True) and this endpoint never triggers any action.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.analytics.advisory import get_ai_advisory
from app.analytics.schemas import AIAdvisoryRequest, AIAdvisoryResult

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/advisory", response_model=AIAdvisoryResult)
def get_advisory(payload: AIAdvisoryRequest) -> AIAdvisoryResult:
    return get_ai_advisory(payload.features, payload.attendance_history)
