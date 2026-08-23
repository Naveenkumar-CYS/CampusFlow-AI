"""
Pydantic schemas for the student risk-classification foundation.

These describe the *public* contract of the AI/ML foundation: what a
caller supplies (``StudentRiskFeaturesInput``) and what they get back
(``RiskPrediction``). Nothing here talks to the database, the event bus,
or automation — see ``app/analytics/__init__.py`` for the Stage 5A scope.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class StudentRiskFeaturesInput(BaseModel):
    """
    Raw input to the risk-classification foundation.

    All fields are optional because, per the Stage 5A brief, this project
    does not currently persist attendance/marks/assignment data anywhere
    (see ``app/models/student.py`` and ``app/models/fee.py`` — neither
    has these columns). Rather than inventing database columns to make
    the model convenient, the ML input schema is deliberately decoupled
    from persistence: a caller (a future Stage 5B integration, a manual
    API call, a test) supplies whatever it currently knows, and missing
    fields are imputed with documented, neutral defaults by
    ``features.prepare_features``.

    Ranges are validated eagerly so obviously-invalid data (e.g. -5%
    attendance) is rejected before it ever reaches the model.
    """

    attendance_percentage: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Percentage of classes attended, 0-100. None if unknown.",
    )
    average_marks: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Average marks/score across recent assessments, 0-100. None if unknown.",
    )
    missed_assignments: int | None = Field(
        default=None,
        ge=0,
        description="Count of missed/late assignments in the current term. None if unknown.",
    )
    fee_overdue_indicator: bool | None = Field(
        default=None,
        description="True if the student currently has an OVERDUE fee (see FeeStatus). None if unknown.",
    )

    @field_validator("missed_assignments")
    @classmethod
    def _sane_missed_assignments(cls, v: int | None) -> int | None:
        if v is not None and v > 100:
            raise ValueError("missed_assignments looks implausible (>100); check the input")
        return v


class RiskPrediction(BaseModel):
    """
    Output of the risk-classification foundation.

    - ``risk_score``: a normalized 0.0-1.0 value derived directly from
      the trained model's class probabilities (see ``risk.py`` for the
      exact formula). 0.0 means the model is fully confident in LOW
      risk, 1.0 means fully confident in HIGH risk.
    - ``risk_level``: a human-readable advisory category obtained by
      thresholding ``risk_score`` (thresholds documented in ``risk.py``).
      This is advisory only, per the architecture doc's "human override
      on any AI-influenced decision" requirement -- it is not consumed
      by any automation in Stage 5A.
    - ``model_version``: fixed identifier of the trained artifact that
      produced this prediction (see ``model.MODEL_VERSION``).
    """

    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    model_version: str


# ---------------------------------------------------------------------
# Stage 5B-1: Attendance Pattern Analysis + AI Advisory Service schemas.
#
# These extend the Stage 5A contract above without changing it -- the
# existing StudentRiskFeaturesInput / RiskPrediction classes and risk.py
# are untouched. See app/analytics/attendance.py and
# app/analytics/advisory.py for the logic that produces these.
# ---------------------------------------------------------------------

AttendancePattern = Literal[
    "STABLE",
    "DECLINING",
    "IMPROVING",
    "SUDDEN_DROP",
    "LOW",
    "INSUFFICIENT_DATA",
]


class AttendanceAnalysis(BaseModel):
    """
    Output of the (non-ML, statistical) attendance pattern analyzer --
    see ``app/analytics/attendance.py`` for the full definitions and
    thresholds behind each ``pattern`` value.
    """

    pattern: AttendancePattern
    observation_count: int = Field(
        ge=0, description="Number of valid (non-missing) observations used."
    )
    attendance_current: float | None = Field(
        default=None, description="Most recent valid observation, if any."
    )
    attendance_average: float | None = Field(
        default=None, description="Mean of all valid observations, if any."
    )
    attendance_change: float | None = Field(
        default=None,
        description=(
            "For SUDDEN_DROP: current minus the prior baseline mean. "
            "For all other patterns with >=2 valid observations: current "
            "minus the earliest valid observation. None when there are "
            "fewer than 2 valid observations to compare."
        ),
    )


class AIAdvisoryRequest(BaseModel):
    """Request body for the optional demonstration endpoint
    (``POST /analytics/advisory`` -- see ``app/api/analytics.py``).
    Combines the Stage 5A feature input with an (optional) ordered,
    oldest-first attendance history for the Stage 5B-1 analyzer."""

    features: StudentRiskFeaturesInput = Field(default_factory=StudentRiskFeaturesInput)
    attendance_history: list[float | None] | None = Field(
        default=None,
        description="Ordered, oldest-first attendance percentages (0-100). "
        "None entries are treated as missing observations.",
    )


class AIAdvisoryResult(BaseModel):
    """
    Combined output of the AI Advisory Service: the Stage 5A ML risk
    prediction plus the attendance pattern analysis, presented together.

    THIS RESULT IS STRICTLY ADVISORY. It identifies risk/patterns and
    may recommend human intervention; it never approves/rejects
    admissions, allocates hostels, finalizes exam results, authorizes
    payments, or otherwise performs an irreversible action -- see
    ``app/analytics/advisory.py`` module docstring for the full policy.
    Nothing in Stage 5B-1 consumes this automatically; automation wiring
    is Stage 5B-2.

    - ``ai_available``: False whenever the Stage 5A model could not be
      loaded or prediction failed. When False, ``risk_score``/
      ``risk_level``/``model_version`` are all None and ``error``
      describes what went wrong -- the service never reports a fabricated
      "successful" prediction after a failure.
    - ``attendance_pattern`` (and the other attendance_* fields) always
      come from the deterministic attendance analyzer and are populated
      independently of whether the ML side succeeded (see Part 4 of the
      Stage 5B-1 brief: a missing/failed model must not block attendance
      insight, and vice versa).
    """

    is_advisory_only: Literal[True] = Field(
        default=True,
        description="Always True. This result is advisory-only and must not "
        "be used to automatically perform irreversible actions.",
    )
    ai_available: bool = Field(
        description="False if the Stage 5A model failed to load or predict."
    )
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)
    risk_level: RiskLevel | None = None
    model_version: str | None = None
    attendance_pattern: AttendancePattern
    attendance_current: float | None = None
    attendance_average: float | None = None
    attendance_change: float | None = None
    advisory_message: str
    error: str | None = Field(
        default=None,
        description="Populated only when ai_available is False; describes "
        "the model-loading/prediction failure.",
    )
