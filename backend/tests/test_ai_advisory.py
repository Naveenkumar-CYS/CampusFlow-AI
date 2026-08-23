"""
Unit tests for the Stage 5B-1 AI Advisory Service
(app/analytics/advisory.py).

Model lifecycle mirrors test_analytics.py (Stage 5A): train once into a
throwaway artifact path, point risk.py's cached loader at it. The main
success-path tests below run the REAL Stage 5A model end-to-end (no
mocking of predict_risk/the estimator) -- only the explicit
failure-path tests substitute a broken model path or a raising stub.
"""
import pytest

from app.analytics import advisory as advisory_module
from app.analytics import model as model_module
from app.analytics import risk as risk_module
from app.analytics import training as training_module
from app.analytics.advisory import get_ai_advisory
from app.analytics.schemas import AIAdvisoryResult, StudentRiskFeaturesInput

VALID_FEATURES = StudentRiskFeaturesInput(
    attendance_percentage=55.0,
    average_marks=42.0,
    missed_assignments=6,
    fee_overdue_indicator=True,
)

DECLINING_HISTORY = [90.0, 86.0, 82.0, 78.0, 74.0]


@pytest.fixture(scope="module")
def trained_model_path(tmp_path_factory):
    scratch_dir = tmp_path_factory.mktemp("advisory_artifacts")
    scratch_path = scratch_dir / "risk_model.joblib"

    dataset = training_module.generate_training_dataset()
    estimator = training_module.train_model(dataset)
    model_module.save_model(estimator, path=scratch_path)

    return scratch_path


@pytest.fixture()
def use_real_model(trained_model_path, monkeypatch):
    """Point the real, trained Stage 5A model at a scratch artifact --
    this is the REAL model/estimator, not a mock."""
    monkeypatch.setattr(risk_module, "MODEL_PATH", trained_model_path)
    risk_module.reset_model_cache()
    yield
    risk_module.reset_model_cache()


@pytest.fixture()
def use_missing_model(tmp_path, monkeypatch):
    """Point at a path where no artifact has ever been trained/saved --
    a genuine (not mocked) ModelNotTrainedError failure path."""
    monkeypatch.setattr(risk_module, "MODEL_PATH", tmp_path / "does_not_exist.joblib")
    risk_module.reset_model_cache()
    yield
    risk_module.reset_model_cache()


# ---------------------------------------------------------------------
# Success path -- REAL Stage 5A model, not mocked
# ---------------------------------------------------------------------


def test_valid_student_input_with_real_model(use_real_model):
    result = get_ai_advisory(VALID_FEATURES, attendance_history=DECLINING_HISTORY)
    assert isinstance(result, AIAdvisoryResult)
    assert result.ai_available is True


def test_risk_score_returned_by_real_model(use_real_model):
    result = get_ai_advisory(VALID_FEATURES, attendance_history=DECLINING_HISTORY)
    assert result.risk_score is not None
    assert 0.0 <= result.risk_score <= 1.0


def test_risk_level_returned_by_real_model(use_real_model):
    result = get_ai_advisory(VALID_FEATURES, attendance_history=DECLINING_HISTORY)
    assert result.risk_level in {"LOW", "MEDIUM", "HIGH"}


def test_model_version_returned(use_real_model):
    result = get_ai_advisory(VALID_FEATURES, attendance_history=DECLINING_HISTORY)
    assert result.model_version == model_module.MODEL_VERSION


def test_attendance_pattern_included_alongside_real_prediction(use_real_model):
    result = get_ai_advisory(VALID_FEATURES, attendance_history=DECLINING_HISTORY)
    assert result.attendance_pattern == "DECLINING"


def test_result_is_deterministic(use_real_model):
    r1 = get_ai_advisory(VALID_FEATURES, attendance_history=DECLINING_HISTORY)
    r2 = get_ai_advisory(VALID_FEATURES, attendance_history=DECLINING_HISTORY)
    assert r1 == r2


def test_uses_stage_5a_model_not_a_duplicate(use_real_model):
    """The advisory service's risk fields must match calling
    risk.predict_risk directly -- proving it reuses the same Stage 5A
    model rather than a separately trained/duplicated classifier."""
    direct = risk_module.predict_risk(VALID_FEATURES)
    result = get_ai_advisory(VALID_FEATURES, attendance_history=DECLINING_HISTORY)
    assert result.risk_score == direct.risk_score
    assert result.risk_level == direct.risk_level
    assert result.model_version == direct.model_version


# ---------------------------------------------------------------------
# Missing / invalid attendance history -- must not break the ML side
# ---------------------------------------------------------------------


def test_missing_attendance_history_does_not_crash_risk_prediction(use_real_model):
    result = get_ai_advisory(VALID_FEATURES, attendance_history=None)
    assert result.ai_available is True
    assert result.risk_score is not None
    assert result.attendance_pattern == "INSUFFICIENT_DATA"


def test_empty_attendance_history_does_not_crash_risk_prediction(use_real_model):
    result = get_ai_advisory(VALID_FEATURES, attendance_history=[])
    assert result.ai_available is True
    assert result.attendance_pattern == "INSUFFICIENT_DATA"


def test_invalid_attendance_values_degrade_gracefully(use_real_model):
    result = get_ai_advisory(VALID_FEATURES, attendance_history=[90.0, -5.0, 80.0])
    # Bad attendance data must not crash the whole advisory call, and
    # must not be silently treated as valid -- it degrades to
    # INSUFFICIENT_DATA with a note in `error`, while the ML side (which
    # doesn't depend on attendance) still succeeds.
    assert result.ai_available is True
    assert result.attendance_pattern == "INSUFFICIENT_DATA"
    assert result.error is not None


def test_invalid_student_features_are_rejected_by_pydantic():
    with pytest.raises(Exception):
        StudentRiskFeaturesInput(attendance_percentage=-10.0)


# ---------------------------------------------------------------------
# Model failure paths (explicit failure-path tests -- mocking allowed here)
# ---------------------------------------------------------------------


def test_model_not_trained_returns_structured_failure(use_missing_model):
    result = get_ai_advisory(VALID_FEATURES, attendance_history=DECLINING_HISTORY)
    assert result.ai_available is False
    assert result.risk_score is None
    assert result.risk_level is None
    assert result.model_version is None
    assert result.error is not None
    # Attendance analysis must still have run despite the ML failure.
    assert result.attendance_pattern == "DECLINING"


def test_model_failure_never_silently_reports_success(use_missing_model):
    result = get_ai_advisory(VALID_FEATURES, attendance_history=DECLINING_HISTORY)
    assert result.ai_available is False
    assert result.advisory_message  # non-empty, explains the situation
    assert "unavailable" in result.advisory_message.lower()


def test_generic_prediction_exception_returns_structured_failure(monkeypatch, use_real_model):
    def _raise(_features):
        raise RuntimeError("simulated prediction failure")

    monkeypatch.setattr(advisory_module, "predict_risk", _raise)
    result = get_ai_advisory(VALID_FEATURES, attendance_history=DECLINING_HISTORY)
    assert result.ai_available is False
    assert result.error is not None
    assert "simulated prediction failure" in result.error


def test_both_ai_and_attendance_failing_still_returns_a_result(use_missing_model):
    result = get_ai_advisory(VALID_FEATURES, attendance_history=[-5.0])
    assert isinstance(result, AIAdvisoryResult)
    assert result.ai_available is False
    assert result.attendance_pattern == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------
# Advisory-only safety (Part 5)
# ---------------------------------------------------------------------


def test_result_is_always_marked_advisory_only(use_real_model):
    result = get_ai_advisory(VALID_FEATURES, attendance_history=DECLINING_HISTORY)
    assert result.is_advisory_only is True


def test_advisory_message_never_claims_an_action_was_taken(use_real_model):
    result = get_ai_advisory(VALID_FEATURES, attendance_history=DECLINING_HISTORY)
    forbidden_phrases = [
        "approved",
        "rejected",
        "allocated",
        "finalized",
        "authorized",
        "has been notified",
    ]
    lowered = result.advisory_message.lower()
    for phrase in forbidden_phrases:
        assert phrase not in lowered


def test_advisory_service_has_no_automation_dependency():
    """Import-time guard: the advisory module must not depend on
    app.automation or app.events (that wiring is Stage 5B-2).

    Inspects the module's actual parsed import statements (AST) rather
    than scanning raw source text, so this checks for a real Python
    dependency and isn't tripped up by the word "automation" appearing
    in prose/docstrings/comments that merely explain the boundary.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(advisory_module))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    for module_name in imported_modules:
        assert not module_name.startswith("app.automation"), (
            f"advisory.py imports {module_name!r} -- it must not depend on app.automation"
        )
        assert not module_name.startswith("app.events"), (
            f"advisory.py imports {module_name!r} -- it must not depend on app.events"
        )
