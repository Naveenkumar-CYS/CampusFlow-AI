"""
Deterministic local training dataset + training routine for the student
risk-classification model.

Dataset
-------
There is no real attendance/marks/assignment data anywhere in this
project (see the note in ``schemas.py``), so this module generates a
small, synthetic, clearly-documented demonstration dataset instead of
pulling from the database or the internet. It is:

    - local          -- pure Python/numpy, no files fetched, no DB query
    - reproducible    -- a fixed ``numpy.random.RandomState`` seed (42),
                          so the exact same dataset (and therefore the
                          exact same trained model) is produced every run
    - documented       -- generation rule spelled out below
    - free of real PII -- every "student" is a synthetic feature tuple
    - varied            -- samples are drawn per target class from
                            distributions that overlap at the edges, so
                            the classifier has to do real work rather
                            than separate cleanly-clustered blobs

Generation rule: for each of the three target classes, feature values
are drawn from a class-appropriate normal distribution (e.g. LOW-risk
students cluster around high attendance/marks and low missed
assignments; HIGH-risk students cluster around the opposite), then
clipped to valid ranges. This is *only* used to build synthetic labeled
training examples -- it is never used at prediction time. Prediction
always goes through the trained scikit-learn estimator (see risk.py);
this module is not a disguised rule engine.

Target
------
``risk_label`` is one of ``LOW`` / ``MEDIUM`` / ``HIGH`` -- the student's
synthetic academic/engagement risk band for this demonstration dataset.

Model
-----
``RandomForestClassifier`` was chosen over a plain ``LogisticRegression``
because the four engineered features plausibly interact non-linearly
(e.g. low attendance matters more when marks are also low, and a fee
overdue flag compounds risk rather than adding to it linearly). A small
forest (50 shallow trees) captures that without overfitting a dataset
this size, stays deterministic given ``random_state``, and produces
well-calibrated-enough ``predict_proba`` output for the risk score. The
saved artifact is a few tens of KB.
"""
from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from app.analytics.features import FEATURE_ORDER
from app.analytics.model import MODEL_VERSION, save_model

# Fixed seed -> fully reproducible dataset and, combined with the
# estimator's own random_state, a fully reproducible trained model.
DATASET_SEED = 42
SAMPLES_PER_CLASS = 40

RISK_LABELS = ("LOW", "MEDIUM", "HIGH")

# Class-conditional generation parameters: (mean, std) per feature, in
# FEATURE_ORDER. Deliberately overlapping so classes aren't trivially
# separable.
_CLASS_PARAMS: dict[str, list[tuple[float, float]]] = {
    "LOW": [
        (92.0, 5.0),   # attendance_percentage
        (82.0, 8.0),   # average_marks
        (0.5, 0.8),    # missed_assignments
        (0.05, 0.22),  # fee_overdue_indicator (Bernoulli-ish via normal + clip)
    ],
    "MEDIUM": [
        (78.0, 7.0),
        (65.0, 9.0),
        (2.5, 1.5),
        (0.30, 0.46),
    ],
    "HIGH": [
        (58.0, 10.0),
        (45.0, 12.0),
        (5.5, 2.2),
        (0.65, 0.48),
    ],
}


@dataclass(frozen=True)
class TrainingDataset:
    X: np.ndarray  # shape (n_samples, len(FEATURE_ORDER))
    y: list[str]   # length n_samples, values in RISK_LABELS


def generate_training_dataset(
    samples_per_class: int = SAMPLES_PER_CLASS, seed: int = DATASET_SEED
) -> TrainingDataset:
    """Deterministically generate the synthetic demonstration dataset."""
    rng = np.random.RandomState(seed)

    rows: list[list[float]] = []
    labels: list[str] = []

    for label in RISK_LABELS:
        params = _CLASS_PARAMS[label]
        for _ in range(samples_per_class):
            attendance = np.clip(rng.normal(*params[0]), 0, 100)
            marks = np.clip(rng.normal(*params[1]), 0, 100)
            missed = np.clip(round(rng.normal(*params[2])), 0, 20)
            fee_overdue = 1.0 if rng.normal(*params[3]) > 0.5 else 0.0
            rows.append([attendance, marks, missed, fee_overdue])
            labels.append(label)

    X = np.array(rows, dtype=float)

    # Deterministic shuffle so classes aren't fed to fit() in contiguous
    # blocks (harmless for RandomForest, but keeps this generic/reusable
    # for other estimators too).
    order = rng.permutation(len(labels))
    X = X[order]
    y = [labels[i] for i in order]

    assert X.shape[1] == len(FEATURE_ORDER)
    return TrainingDataset(X=X, y=y)


def train_model(dataset: TrainingDataset) -> RandomForestClassifier:
    """
    Fit a RandomForestClassifier on the given dataset.

    training data -> feature matrix (dataset.X) -> target (dataset.y)
    -> model.fit() -> trained estimator
    """
    estimator = RandomForestClassifier(
        n_estimators=50,
        max_depth=5,
        random_state=42,
    )
    estimator.fit(dataset.X, dataset.y)
    return estimator


def train_and_save() -> RandomForestClassifier:
    """
    Full training pipeline: generate the deterministic dataset, fit the
    estimator, persist it. Intended to be run intentionally/offline (a
    script or a test), never on the request path -- see risk.py, which
    only ever *loads* the saved artifact.
    """
    dataset = generate_training_dataset()
    estimator = train_model(dataset)
    save_model(estimator)
    return estimator


if __name__ == "__main__":
    trained = train_and_save()
    print(f"Trained {trained.__class__.__name__} (model_version={MODEL_VERSION}) and saved artifact.")
