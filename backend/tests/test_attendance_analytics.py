"""
Unit tests for the Stage 5B-1 attendance pattern analyzer
(app/analytics/attendance.py).

Pure statistics, no ML, no DB, no event bus -- same "standalone,
importable, no external services" property as test_analytics.py (Stage
5A). See attendance.py's module docstring for the exact pattern
definitions and thresholds being exercised here.
"""
import pytest

from app.analytics.attendance import AttendanceValueError, analyze_attendance
from app.analytics.schemas import AttendanceAnalysis

ALL_PATTERNS = {
    "STABLE",
    "DECLINING",
    "IMPROVING",
    "SUDDEN_DROP",
    "LOW",
    "INSUFFICIENT_DATA",
}


def _analyze(history):
    result = analyze_attendance(history)
    assert isinstance(result, AttendanceAnalysis)
    assert result.pattern in ALL_PATTERNS
    return result


# ---------------------------------------------------------------------
# Empty / too-little data
# ---------------------------------------------------------------------


def test_empty_history_is_insufficient_data():
    result = _analyze([])
    assert result.pattern == "INSUFFICIENT_DATA"
    assert result.observation_count == 0
    assert result.attendance_current is None
    assert result.attendance_average is None
    assert result.attendance_change is None


def test_none_history_is_insufficient_data():
    result = _analyze(None)
    assert result.pattern == "INSUFFICIENT_DATA"
    assert result.observation_count == 0


def test_one_observation_is_insufficient_data():
    result = _analyze([90.0])
    assert result.pattern == "INSUFFICIENT_DATA"
    assert result.observation_count == 1
    # Still reports what it can, per Part 4 (don't hide known data).
    assert result.attendance_current == 90.0
    assert result.attendance_average == 90.0


def test_two_observations_can_be_classified_but_not_as_trend_or_drop():
    # Two points are enough for STABLE/LOW, but not enough for
    # SUDDEN_DROP (needs a baseline of >=2 prior points) or a fitted
    # trend (needs >=4 points) -- see MIN_FOR_SUDDEN_DROP/MIN_FOR_TREND.
    result = _analyze([88.0, 90.0])
    assert result.pattern in {"STABLE", "LOW"}
    assert result.observation_count == 2


# ---------------------------------------------------------------------
# Core patterns
# ---------------------------------------------------------------------


def test_stable_attendance():
    result = _analyze([90.0, 88.0, 91.0, 89.0, 90.0])
    assert result.pattern == "STABLE"
    assert result.attendance_current == 90.0


def test_declining_attendance():
    result = _analyze([90.0, 86.0, 82.0, 78.0, 74.0])
    assert result.pattern == "DECLINING"
    assert result.attendance_change is not None
    assert result.attendance_change < 0


def test_improving_attendance():
    result = _analyze([70.0, 74.0, 78.0, 82.0, 86.0])
    assert result.pattern == "IMPROVING"
    assert result.attendance_change is not None
    assert result.attendance_change > 0


def test_sudden_drop():
    result = _analyze([90.0, 88.0, 91.0, 40.0])
    assert result.pattern == "SUDDEN_DROP"
    assert result.attendance_current == 40.0
    assert result.attendance_change is not None
    assert result.attendance_change < 0


def test_low_attendance():
    result = _analyze([60.0, 58.0, 62.0, 59.0, 61.0])
    assert result.pattern == "LOW"
    assert result.attendance_average < 75.0


def test_insufficient_data_pattern_explicitly():
    result = _analyze([50.0])
    assert result.pattern == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------


def test_constant_values_are_stable_when_above_threshold():
    result = _analyze([80.0, 80.0, 80.0, 80.0])
    assert result.pattern == "STABLE"
    assert result.attendance_change == 0.0


def test_constant_values_below_threshold_are_low():
    result = _analyze([60.0, 60.0, 60.0, 60.0])
    assert result.pattern == "LOW"


def test_noisy_values_without_clear_trend_do_not_report_a_trend():
    # High variance, no consistent direction, mean comfortably above the
    # LOW threshold -- should NOT be misclassified as DECLINING/IMPROVING.
    result = _analyze([85.0, 70.0, 95.0, 72.0, 88.0])
    assert result.pattern not in {"DECLINING", "IMPROVING"}


def test_missing_observations_are_filtered_not_treated_as_zero():
    with_gaps = _analyze([90.0, None, 85.0, None, 80.0, 75.0])
    without_gaps = _analyze([90.0, 85.0, 80.0, 75.0])
    assert with_gaps.observation_count == 4
    assert with_gaps.pattern == without_gaps.pattern
    assert with_gaps.attendance_average == without_gaps.attendance_average


def test_all_missing_observations_is_insufficient_data():
    result = _analyze([None, None, None])
    assert result.pattern == "INSUFFICIENT_DATA"
    assert result.observation_count == 0


@pytest.mark.parametrize("bad_value", [-5.0, -0.01, 100.01, 150.0])
def test_invalid_values_are_rejected_not_silently_accepted(bad_value):
    with pytest.raises(AttendanceValueError):
        analyze_attendance([90.0, bad_value, 85.0])


def test_valid_boundary_values_are_accepted():
    # 0 and 100 are the physically valid extremes, not invalid.
    result = _analyze([0.0, 100.0])
    assert result.pattern in ALL_PATTERNS


# ---------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------


def test_analysis_is_deterministic():
    history = [88.0, 85.0, 80.0, 76.0, 71.0]
    r1 = analyze_attendance(history)
    r2 = analyze_attendance(history)
    assert r1 == r2
