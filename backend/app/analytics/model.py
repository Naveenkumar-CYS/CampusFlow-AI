"""
Model persistence for the student risk-classification foundation.

Keeps the trained scikit-learn estimator as a small joblib artifact on
disk, project-local, with no internet dependency. Loading is separate
from training on purpose: the application loads the already-trained
artifact on every prediction; it never retrains on the request path
(see risk.py / training.py).
"""
from pathlib import Path

import joblib
from sklearn.base import ClassifierMixin

# Fixed, meaningful version for the current model/feature-schema
# combination. Bump this by hand whenever the training data, feature
# set, or estimator changes in a way that could change predictions --
# never generate it automatically (e.g. from a timestamp or hash).
MODEL_VERSION = "1.0"

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "risk_model.joblib"


class ModelNotTrainedError(RuntimeError):
    """Raised when a prediction is requested but no trained artifact exists yet."""


def save_model(estimator: ClassifierMixin, path: Path = MODEL_PATH) -> Path:
    """Persist a trained estimator to ``path`` (project-local, lightweight)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(estimator, path)
    return path


def load_model(path: Path = MODEL_PATH) -> ClassifierMixin:
    """
    Load a previously-trained estimator from ``path``.

    Raises ``ModelNotTrainedError`` (rather than letting a raw
    ``FileNotFoundError`` bubble up) if training hasn't been run yet, so
    callers get a clear, actionable message -- see
    ``app/analytics/training.py`` / ``python -m app.analytics.training``.
    """
    if not path.exists():
        raise ModelNotTrainedError(
            f"No trained model artifact at {path}. Run "
            "`python -m app.analytics.training` to train and save one first."
        )
    return joblib.load(path)
