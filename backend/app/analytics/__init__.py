"""
AI/Analytics foundation (Stage 5A).

This package implements the standalone AI/ML foundation described in
CampusFlow_AI_Architecture.md section 7 ("AI/ML Role") — specifically the
first responsibility listed there:

    "At-risk student detection from attendance + academic trend data
    (classification model, e.g. logistic regression / gradient boosting
    on engineered features)"

Scope of Stage 5A (this package):
    - a small, deterministic, local training dataset (``training.py``)
    - a real scikit-learn classifier, trained via ``model.fit()``
    - feature preparation / validation (``features.py``)
    - model persistence + loading (``model.py``)
    - a risk-prediction service returning a score, level and model
      version (``risk.py``)

Explicitly OUT of scope for Stage 5A (see architecture doc section 6/7 —
this is Stage 5B):
    - subscribing to the Redis event bus / Event Processor
    - the Rule Engine / Workflow Engine / Action Executor
    - the Notification Service
    - the ``advisory_flags`` write-back table
    - any automation wiring at all

This package has no import-time dependency on ``app.events`` or
``app.automation`` and is safe to import and use standalone.
"""
