"""
Attendance pattern analysis (Stage 5B-1, Part 1).

    historical attendance observations -> analyze_attendance() -> AttendanceAnalysis

IMPORTANT -- this is NOT machine learning. It is deterministic
statistical/analytical logic over a sequence of attendance percentages
(mean, trend via ordinary-least-squares slope, and a most-recent-vs-baseline
comparison). It is deliberately kept separate from the Stage 5A ML model
(``app/analytics/risk.py``) so that "the model said X" and "the numbers
say X" are never confused with one another. ``app/analytics/advisory.py``
is the only place the two are combined, and even there each contributes
its own clearly-labelled field.

There is no persisted attendance history anywhere in this project yet
(see the note in ``schemas.py`` / Stage 5A) -- an ``AttendanceService`` /
database table is Stage 5B-2+ territory. So this module accepts the
history directly as an ordered sequence of observations, oldest first,
e.g. ``[90, 88, 85, 81, 75]``, exactly as described in the Stage 5B-1
brief. Each observation is either a percentage in ``[0, 100]`` or
``None`` for a missing/unrecorded observation (see EDGE CASES below).

--------------------------------------------------------------------
PATTERN DEFINITIONS (documented, not arbitrary)
--------------------------------------------------------------------
Applied in this order of precedence -- SUDDEN_DROP is checked first
because it is the most urgent/actionable signal and can co-occur with
what would otherwise look like a mild decline or a low-but-stable
average; DECLINING/IMPROVING (trend) is checked next; LOW is checked
only once neither of those explains the data; STABLE is the default.

    INSUFFICIENT_DATA
        Fewer than MIN_OBSERVATIONS (2) valid (non-missing) observations.
        There simply isn't enough data to say anything reliable.

    SUDDEN_DROP
        Requires at least MIN_FOR_SUDDEN_DROP (3) valid observations.
        The most recent observation is at least SUDDEN_DROP_THRESHOLD
        (15) percentage points below the mean of all *prior* valid
        observations (the "baseline"). This flags a sharp, single-step
        change -- e.g. a student who was fine and then missed a block of
        classes -- which a smoothed trend line would dilute and might
        miss entirely.

    DECLINING / IMPROVING
        Requires at least MIN_FOR_TREND (4) valid observations (fewer
        points make a fitted trend line indistinguishable from noise).
        An ordinary-least-squares line is fit through (index, value) for
        the valid observations; the fitted line's total change from
        first to last position is compared against
        TREND_CHANGE_THRESHOLD (10 percentage points). A total fitted
        change <= -10 is DECLINING, >= +10 is IMPROVING. Using the
        fitted line's span (not the raw first/last values) makes this
        resistant to noise in the endpoints specifically -- a noisy
        single low or high point at either end doesn't flip the
        classification if the overall trend of the fitted line is flat.

    LOW
        Not SUDDEN_DROP/DECLINING/IMPROVING, and the mean of all valid
        observations is below LOW_THRESHOLD (75.0 -- the same
        attendance policy threshold already used by the Rule Engine,
        see ``app/automation/rules.py::_attendance_below_75``, kept
        consistent rather than inventing a second number for the same
        idea). Persistently low but not sharply dropping or trending.

    STABLE
        None of the above: attendance is holding roughly steady at a
        non-low level.

--------------------------------------------------------------------
EDGE CASES
--------------------------------------------------------------------
    empty history / None            -> INSUFFICIENT_DATA
    one observation                 -> INSUFFICIENT_DATA
    two observations                -> pattern from {LOW, STABLE,
                                        INSUFFICIENT_DATA} only -- too
                                        few points for SUDDEN_DROP (needs
                                        a baseline) or a trend fit
    constant values                 -> STABLE (or LOW if the constant
                                        value is itself below threshold)
    noisy values                    -> falls through to LOW/STABLE
                                        unless the OLS fit clears
                                        TREND_CHANGE_THRESHOLD -- noise
                                        alone should not look like a
                                        trend
    missing observations (None)     -> filtered out before analysis;
                                        only valid observations count
                                        toward MIN_OBSERVATIONS etc.
    values below 0 or above 100     -> raises AttendanceValueError;
                                        never silently accepted (an
                                        "attendance" of -5% or 130% is a
                                        data-entry bug, not a signal)
"""
from __future__ import annotations

import numpy as np

from app.analytics.schemas import AttendanceAnalysis, AttendancePattern

# -- Documented thresholds (see module docstring for rationale) --------
MIN_OBSERVATIONS = 2
MIN_FOR_SUDDEN_DROP = 3
MIN_FOR_TREND = 4

LOW_THRESHOLD = 75.0
TREND_CHANGE_THRESHOLD = 10.0
SUDDEN_DROP_THRESHOLD = 15.0


class AttendanceValueError(ValueError):
    """Raised when a supplied attendance observation is out of the
    physically-possible [0, 100] range. Attendance analysis never
    silently accepts an impossible percentage."""


def _validate_and_filter(history: list[float | None] | None) -> list[float]:
    """Drop missing (``None``) observations; raise on out-of-range
    values. Order is preserved (oldest observation first)."""
    if not history:
        return []

    valid: list[float] = []
    for i, value in enumerate(history):
        if value is None:
            continue  # missing observation -- simply not counted
        if value < 0 or value > 100:
            raise AttendanceValueError(
                f"attendance observation at index {i} is {value!r}, which is outside "
                "the physically-possible 0-100 range"
            )
        valid.append(float(value))
    return valid


def _fitted_trend_change(values: list[float]) -> float:
    """Total change (last - first) predicted by an OLS line fit through
    (index, value). Used instead of the raw endpoints so a single noisy
    point doesn't dominate the classification."""
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    fitted_first = slope * x[0] + intercept
    fitted_last = slope * x[-1] + intercept
    return float(fitted_last - fitted_first)


def analyze_attendance(history: list[float | None] | None) -> AttendanceAnalysis:
    """
    Classify an ordered (oldest-first) sequence of attendance percentage
    observations into one of the documented ``AttendancePattern`` values.

    This is deterministic statistics, not a trained model -- see the
    module docstring. Raises ``AttendanceValueError`` if any supplied
    observation is outside [0, 100]; never crashes on empty/short/
    missing input (see EDGE CASES above), returning INSUFFICIENT_DATA
    instead.
    """
    valid = _validate_and_filter(history)
    n = len(valid)

    current = valid[-1] if n >= 1 else None
    average = float(np.mean(valid)) if n >= 1 else None

    if n < MIN_OBSERVATIONS:
        return AttendanceAnalysis(
            pattern="INSUFFICIENT_DATA",
            observation_count=n,
            attendance_current=current,
            attendance_average=average,
            attendance_change=None,
        )

    change = current - valid[0]

    # 1. SUDDEN_DROP -- most recent value far below the baseline of
    #    everything before it.
    if n >= MIN_FOR_SUDDEN_DROP:
        baseline = float(np.mean(valid[:-1]))
        if baseline - current >= SUDDEN_DROP_THRESHOLD:
            return AttendanceAnalysis(
                pattern="SUDDEN_DROP",
                observation_count=n,
                attendance_current=current,
                attendance_average=average,
                attendance_change=current - baseline,
            )

    # 2. DECLINING / IMPROVING -- meaningful OLS trend over the window.
    if n >= MIN_FOR_TREND:
        fitted_change = _fitted_trend_change(valid)
        if fitted_change <= -TREND_CHANGE_THRESHOLD:
            return AttendanceAnalysis(
                pattern="DECLINING",
                observation_count=n,
                attendance_current=current,
                attendance_average=average,
                attendance_change=change,
            )
        if fitted_change >= TREND_CHANGE_THRESHOLD:
            return AttendanceAnalysis(
                pattern="IMPROVING",
                observation_count=n,
                attendance_current=current,
                attendance_average=average,
                attendance_change=change,
            )

    # 3. LOW -- persistently below the institutional threshold.
    if average is not None and average < LOW_THRESHOLD:
        return AttendanceAnalysis(
            pattern="LOW",
            observation_count=n,
            attendance_current=current,
            attendance_average=average,
            attendance_change=change,
        )

    # 4. STABLE -- default: no drop, no trend, not persistently low.
    return AttendanceAnalysis(
        pattern="STABLE",
        observation_count=n,
        attendance_current=current,
        attendance_average=average,
        attendance_change=change,
    )
