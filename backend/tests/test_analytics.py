"""
Unit tests for the Stage 5A AI/ML foundation (app/analytics).

Unlike test_api.py/test_fee.py, these tests do NOT need a running
Postgres/Redis -- app/analytics has no database or event-bus dependency
at all, so this module is importable and fully testable standalone.

Model lifecycle for these tests: train once (module-scoped fixture) into
a throwaway artifact path (so we never depend on / clobber whatever is
already on disk), then exercise loading + prediction against it.
"""
import numpy as np
import pytest
from sklearn.base import ClassifierMixin

from app.analytics import model as model_module
from app.analytics import risk as risk_module
from app.analytics import training as training_module
from app.analytics.features import DEFAULT_VALUES, FEATURE_ORDER, prepare_features
from app.analytics.schemas import RiskPrediction, StudentRiskFeaturesInput

VALID_FEATURES = StudentRiskFeaturesInput(
    attendance_percentage=55.0,
    average_marks=42.0,
    missed_assignments=6,
    fee_overdue_indicator=True,
)


@pytest.fixture(scope="module")
def trained_model_path(tmp_path_factory):
    """Train the model once and point model.py's paths at a scratch file."""
    scratch_dir = tmp_path_factory.mktemp("analytics_artifacts")
    scratch_path = scratch_dir / "risk_model.joblib"

    dataset = training_module.generate_training_dataset()
    estimator = training_module.train_model(dataset)
    model_module.save_model(estimator, path=scratch_path)

    return scratch_path


@pytest.fixture()
def use_scratch_model(trained_model_path, monkeypatch):
    """Point risk.py's cached loader at the scratch artifact for a test."""
    monkeypatch.setattr(risk_module, "MODEL_PATH", trained_model_path)
    risk_module.reset_model_cache()
    yield
    risk_module.reset_model_cache()


# ---------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------


def test_sklearn_import_works():
    import sklearn  # noqa: F401
    from sklearn.ensemble import RandomForestClassifier  # noqa: F401


# ---------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------


def test_training_dataset_is_well_formed():
    dataset = training_module.generate_training_dataset()
    assert dataset.X.shape[0] == len(dataset.y)
    assert dataset.X.shape[1] == len(FEATURE_ORDER)
    assert set(dataset.y) == {"LOW", "MEDIUM", "HIGH"}


def test_training_dataset_is_deterministic():
    d1 = training_module.generate_training_dataset()
    d2 = training_module.generate_training_dataset()
    assert np.array_equal(d1.X, d2.X)
    assert d1.y == d2.y


def test_training_succeeds_and_returns_real_sklearn_estimator():
    dataset = training_module.generate_training_dataset()
    estimator = training_module.train_model(dataset)
    assert isinstance(estimator, ClassifierMixin)
    # A genuinely fit estimator exposes learned attributes like classes_.
    assert set(estimator.classes_) == {"LOW", "MEDIUM", "HIGH"}


def test_model_can_be_saved(tmp_path):
    dataset = training_module.generate_training_dataset()
    estimator = training_module.train_model(dataset)
    path = model_module.save_model(estimator, path=tmp_path / "m.joblib")
    assert path.exists()
    assert path.stat().st_size > 0


# ---------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------


def test_saved_model_can_be_loaded(trained_model_path):
    loaded = model_module.load_model(path=trained_model_path)
    assert isinstance(loaded, ClassifierMixin)


def test_loaded_model_can_predict(trained_model_path):
    loaded = model_module.load_model(path=trained_model_path)
    X = prepare_features(VALID_FEATURES)
    prediction = loaded.predict(X)
    assert prediction[0] in {"LOW", "MEDIUM", "HIGH"}


def test_loading_missing_model_raises_clear_error(tmp_path):
    with pytest.raises(model_module.ModelNotTrainedError):
        model_module.load_model(path=tmp_path / "does_not_exist.joblib")


# ---------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------


def test_predict_risk_returns_valid_prediction(use_scratch_model):
    result = risk_module.predict_risk(VALID_FEATURES)
    assert isinstance(result, RiskPrediction)


def test_risk_score_in_documented_range(use_scratch_model):
    result = risk_module.predict_risk(VALID_FEATURES)
    assert 0.0 <= result.risk_score <= 1.0


def test_risk_level_is_valid_category(use_scratch_model):
    result = risk_module.predict_risk(VALID_FEATURES)
    assert result.risk_level in {"LOW", "MEDIUM", "HIGH"}


def test_model_version_present(use_scratch_model):
    result = risk_module.predict_risk(VALID_FEATURES)
    assert result.model_version == model_module.MODEL_VERSION
    assert result.model_version  # non-empty


def test_high_risk_profile_scores_high(use_scratch_model):
    """A profile matching the HIGH-risk training distribution should
    score meaningfully higher than a profile matching LOW."""
    high_risk = StudentRiskFeaturesInput(
        attendance_percentage=40.0,
        average_marks=30.0,
        missed_assignments=9,
        fee_overdue_indicator=True,
    )
    low_risk = StudentRiskFeaturesInput(
        attendance_percentage=97.0,
        average_marks=90.0,
        missed_assignments=0,
        fee_overdue_indicator=False,
    )
    high_result = risk_module.predict_risk(high_risk)
    low_result = risk_module.predict_risk(low_risk)
    assert high_result.risk_score > low_result.risk_score


# ---------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------


def test_prediction_is_deterministic(use_scratch_model):
    result1 = risk_module.predict_risk(VALID_FEATURES)
    result2 = risk_module.predict_risk(VALID_FEATURES)
    assert result1 == result2


# ---------------------------------------------------------------------
# Validation / missing data
# ---------------------------------------------------------------------


def test_missing_fields_are_imputed_not_invented():
    empty_input = StudentRiskFeaturesInput()
    features = prepare_features(empty_input)
    expected = [DEFAULT_VALUES[name] for name in FEATURE_ORDER]
    assert features.tolist()[0] == expected


def test_partial_missing_fields_use_defaults_for_missing_only():
    partial = StudentRiskFeaturesInput(attendance_percentage=88.0)
    features = prepare_features(partial)
    row = dict(zip(FEATURE_ORDER, features.tolist()[0]))
    assert row["attendance_percentage"] == 88.0
    assert row["average_marks"] == DEFAULT_VALUES["average_marks"]
    assert row["missed_assignments"] == DEFAULT_VALUES["missed_assignments"]
    assert row["fee_overdue_indicator"] == DEFAULT_VALUES["fee_overdue_indicator"]


def test_missing_values_do_not_crash_prediction(use_scratch_model):
    sparse = StudentRiskFeaturesInput(attendance_percentage=50.0)
    result = risk_module.predict_risk(sparse)
    assert isinstance(result, RiskPrediction)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"attendance_percentage": -5.0},
        {"attendance_percentage": 150.0},
        {"average_marks": -1.0},
        {"average_marks": 101.0},
        {"missed_assignments": -1},
    ],
)
def test_invalid_input_is_rejected(kwargs):
    with pytest.raises(Exception):
        StudentRiskFeaturesInput(**kwargs)
