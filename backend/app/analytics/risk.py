"""
Risk-prediction service: the public entry point of the AI/ML foundation.

    StudentRiskFeaturesInput -> features.prepare_features -> loaded model
        -> model.predict_proba -> risk_score -> risk_level -> RiskPrediction

Loads the trained artifact once (cached) and reuses it for every
prediction; it never retrains on the request path.
"""
from functools import lru_cache

from sklearn.base import ClassifierMixin

from app.analytics.features import prepare_features
from app.analytics.model import MODEL_PATH, MODEL_VERSION, load_model
from app.analytics.schemas import RiskLevel, RiskPrediction, StudentRiskFeaturesInput

# Ordinal weight used to collapse the model's LOW/MEDIUM/HIGH class
# probabilities into a single 0.0-1.0 risk_score:
#
#   risk_score = sum(P(class) * ORDINAL_WEIGHT[class] for class in classes)
#
# e.g. a model that's 100% confident in LOW gives 0.0; 100% confident in
# HIGH gives 1.0; a model split 50/50 between MEDIUM and HIGH gives
# 0.5*0.5 + 0.5*1.0 = 0.75. This uses the model's actual predicted
# probabilities (not a hand-written formula over the raw features) --
# it's a documented aggregation of genuine model output, not fabricated
# confidence.
ORDINAL_WEIGHT: dict[str, float] = {"LOW": 0.0, "MEDIUM": 0.5, "HIGH": 1.0}

# risk_score -> risk_level thresholds. The three model classes are
# evenly spaced on [0, 1] via ORDINAL_WEIGHT (0.0 / 0.5 / 1.0), so the
# boundaries are placed halfway between adjacent class weights.
LOW_MEDIUM_THRESHOLD = 0.25
MEDIUM_HIGH_THRESHOLD = 0.75


def _score_to_level(score: float) -> RiskLevel:
    if score < LOW_MEDIUM_THRESHOLD:
        return "LOW"
    if score < MEDIUM_HIGH_THRESHOLD:
        return "MEDIUM"
    return "HIGH"


@lru_cache(maxsize=1)
def _get_model() -> ClassifierMixin:
    """Load the trained artifact once per process and cache it."""
    return load_model(MODEL_PATH)


def reset_model_cache() -> None:
    """Clear the cached model (used by tests after retraining)."""
    _get_model.cache_clear()


def predict_risk(features: StudentRiskFeaturesInput) -> RiskPrediction:
    """
    Run a single student's features through the trained model and return
    an advisory risk score/level. Raises ``ModelNotTrainedError`` (from
    ``model.load_model``) if no artifact has been trained yet.
    """
    estimator = _get_model()
    X = prepare_features(features)

    proba = estimator.predict_proba(X)[0]
    class_labels = list(estimator.classes_)

    risk_score = float(
        sum(p * ORDINAL_WEIGHT[label] for p, label in zip(proba, class_labels))
    )
    # Guard against float drift outside [0, 1] from summation.
    risk_score = max(0.0, min(1.0, risk_score))

    return RiskPrediction(
        risk_score=risk_score,
        risk_level=_score_to_level(risk_score),
        model_version=MODEL_VERSION,
    )
