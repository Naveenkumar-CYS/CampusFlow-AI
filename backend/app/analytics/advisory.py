"""
AI Advisory Service (Stage 5B-1, Part 2/3/4/5).

    Student features + attendance history
              |
              +--> app.analytics.risk.predict_risk()   (existing Stage 5A model)
              |
              +--> app.analytics.attendance.analyze_attendance()  (Part 1, this stage)
              |
              v
        AIAdvisoryResult (schemas.py)

This module is a thin combiner. It does NOT create, train, or duplicate
a classifier -- it calls the existing Stage 5A ``predict_risk`` exactly
as-is (same model, same feature set, same estimator) and pairs the
result with the attendance pattern analysis from ``attendance.py``. See
``app/analytics/__init__.py`` / ``risk.py`` for the Stage 5A model
itself, which is untouched by Stage 5B-1.

--------------------------------------------------------------------
FAILURE HANDLING (Part 4)
--------------------------------------------------------------------
- Stage 5A model can't load / prediction fails
    -> ``ai_available=False``, ``risk_score``/``risk_level``/
       ``model_version`` all None, ``error`` set. The attendance side of
       the result is still computed and returned -- a broken model must
       not hide attendance insight that's otherwise available.
- Attendance history missing/empty/unavailable
    -> does NOT raise and does NOT block the risk prediction;
       ``attendance_pattern`` becomes ``INSUFFICIENT_DATA`` (or whatever
       ``analyze_attendance`` returns for that input) and the ML side
       proceeds normally.
- Attendance history present but contains out-of-range values
    -> ``analyze_attendance`` raises ``AttendanceValueError`` for a
       *direct* caller (see attendance.py), but this service treats that
       the same as "attendance unavailable": it is caught here, degrades
       to ``INSUFFICIENT_DATA`` with a note, and -- per the same
       "don't crash the risk prediction" rule -- never prevents the ML
       side from still returning a result.
- Both fail
    -> ``ai_available=False`` and ``attendance_pattern="INSUFFICIENT_DATA"``
       together; the result is still returned (never raises to the
       caller), with ``error`` explaining the ML failure.

--------------------------------------------------------------------
ADVISORY SAFETY (Part 5)
--------------------------------------------------------------------
Every ``AIAdvisoryResult`` carries ``is_advisory_only=True``. This
service only ever identifies risk/patterns and phrases a recommendation
for human review in ``advisory_message`` -- see the module docstring in
``schemas.py``. It never calls anything in the automation package and
holds no capability to approve/reject admissions, allocate hostels, finalize
exam results, authorize payments, or otherwise mutate academic records.
Wiring this into automation (so a workflow can *act* on the advisory) is
explicitly Stage 5B-2, not here.
"""
from __future__ import annotations

from app.analytics.attendance import AttendanceValueError, analyze_attendance
from app.analytics.model import ModelNotTrainedError
from app.analytics.risk import predict_risk
from app.analytics.schemas import (
    AIAdvisoryResult,
    AttendanceAnalysis,
    StudentRiskFeaturesInput,
)


def _safe_attendance_analysis(
    attendance_history: list[float | None] | None,
) -> tuple[AttendanceAnalysis, str | None]:
    """
    Run the attendance analyzer without ever raising. Returns
    (analysis, note) where ``note`` is a short human-readable explanation
    if the input had to be degraded (e.g. invalid values were present),
    or None if analysis ran normally.
    """
    try:
        return analyze_attendance(attendance_history), None
    except AttendanceValueError as exc:
        # Per Part 4: don't let a bad/unavailable attendance history
        # crash or block the risk prediction -- degrade gracefully.
        degraded = analyze_attendance(None)  # -> INSUFFICIENT_DATA, all-None fields
        return degraded, f"attendance history ignored: {exc}"


def _advisory_message(
    ai_available: bool,
    risk_level: str | None,
    attendance_pattern: str,
) -> str:
    """Build a short, clearly-advisory human-readable summary. Never
    phrases anything as a decision/action -- only as a recommendation
    for human review, per Part 5."""
    if not ai_available:
        if attendance_pattern in ("DECLINING", "SUDDEN_DROP", "LOW"):
            return (
                f"AI risk model unavailable. Attendance pattern is {attendance_pattern}; "
                "a human advisor should review this student directly."
            )
        return (
            "AI risk model unavailable. Insufficient signal to advise -- "
            "no automatic conclusion should be drawn."
        )

    concern_patterns = {"DECLINING", "SUDDEN_DROP", "LOW"}
    if risk_level == "HIGH" or attendance_pattern in concern_patterns:
        return (
            f"Advisory only: model risk level is {risk_level} and attendance pattern is "
            f"{attendance_pattern}. Recommend human academic advisor review; this is not "
            "an automatic decision."
        )
    if risk_level == "MEDIUM":
        return (
            f"Advisory only: model risk level is {risk_level} with {attendance_pattern} "
            "attendance. Worth a routine check-in; no urgent action indicated."
        )
    return (
        f"Advisory only: model risk level is {risk_level} with {attendance_pattern} "
        "attendance. No intervention indicated at this time."
    )


def get_ai_advisory(
    features: StudentRiskFeaturesInput,
    attendance_history: list[float | None] | None = None,
) -> AIAdvisoryResult:
    """
    The AI Advisory Service's single entry point.

    Combines the existing Stage 5A risk prediction with the Stage 5B-1
    attendance pattern analysis into one structured, advisory-only
    result. Never raises for "expected" failure modes (model not
    trained, prediction error, missing/invalid attendance) -- see the
    module docstring's FAILURE HANDLING section. Deterministic: the same
    inputs against the same trained model artifact always produce the
    same output (Stage 5A's model is itself deterministic; see
    training.py).
    """
    attendance_analysis, attendance_note = _safe_attendance_analysis(attendance_history)

    try:
        risk_prediction = predict_risk(features)
        ai_available = True
        risk_score = risk_prediction.risk_score
        risk_level = risk_prediction.risk_level
        model_version = risk_prediction.model_version
        error = attendance_note  # surface a degraded-attendance note even on ML success
    except ModelNotTrainedError as exc:
        ai_available = False
        risk_score = None
        risk_level = None
        model_version = None
        error = str(exc) if attendance_note is None else f"{exc}; {attendance_note}"
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: any prediction
        # failure must degrade to a structured failure, never crash the
        # caller or silently report a fabricated success (Part 4).
        ai_available = False
        risk_score = None
        risk_level = None
        model_version = None
        error = str(exc) if attendance_note is None else f"{exc}; {attendance_note}"

    message = _advisory_message(ai_available, risk_level, attendance_analysis.pattern)

    return AIAdvisoryResult(
        ai_available=ai_available,
        risk_score=risk_score,
        risk_level=risk_level,
        model_version=model_version,
        attendance_pattern=attendance_analysis.pattern,
        attendance_current=attendance_analysis.attendance_current,
        attendance_average=attendance_analysis.attendance_average,
        attendance_change=attendance_analysis.attendance_change,
        advisory_message=message,
        error=error,
    )
