"""
Feature preparation for the student risk-classification model.

Converts a validated ``StudentRiskFeaturesInput`` into the fixed-order
numeric feature vector the scikit-learn estimator expects. This is the
*only* place feature engineering happens -- API/service code should never
build a feature vector by hand.
"""
import numpy as np

from app.analytics.schemas import StudentRiskFeaturesInput

# Canonical feature order. The trained model was fit on columns in
# exactly this order (see training.py) -- changing this list requires
# retraining the model, so it lives in one place and everything else
# imports it rather than hardcoding column positions.
FEATURE_ORDER: list[str] = [
    "attendance_percentage",
    "average_marks",
    "missed_assignments",
    "fee_overdue_indicator",
]

# Missing-value strategy: documented, fixed imputation values -- never
# silently invented per-call. These are deliberately "neutral" values
# that don't push a prediction toward either extreme:
#   - attendance_percentage: 75.0, a common minimum-attendance policy
#     threshold (see the Rule Engine's attendance check in the
#     architecture doc) used here purely as a neutral midpoint, not as
#     a pass/fail cutoff.
#   - average_marks: 60.0, a generic "average" pass mark midpoint.
#   - missed_assignments: 0, the conservative assumption when unknown.
#   - fee_overdue_indicator: False (0), the conservative assumption
#     when unknown (absence of evidence of overdue fees).
DEFAULT_VALUES: dict[str, float] = {
    "attendance_percentage": 75.0,
    "average_marks": 60.0,
    "missed_assignments": 0.0,
    "fee_overdue_indicator": 0.0,
}


def prepare_features(features: StudentRiskFeaturesInput) -> np.ndarray:
    """
    Turn a validated input into a ``(1, len(FEATURE_ORDER))`` float
    array, in ``FEATURE_ORDER``, with missing values imputed per
    ``DEFAULT_VALUES``.

    Validation of ranges (e.g. 0-100 for percentages) already happened
    on ``StudentRiskFeaturesInput`` construction (pydantic field
    validators) -- this function's only job is imputation + ordering.
    """
    raw = features.model_dump()

    row: list[float] = []
    for name in FEATURE_ORDER:
        value = raw.get(name)
        if value is None:
            value = DEFAULT_VALUES[name]
        elif isinstance(value, bool):
            value = float(value)
        row.append(float(value))

    return np.array([row], dtype=float)
