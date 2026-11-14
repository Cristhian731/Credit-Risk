"""Feature schema shared by the training code and the web app.

FEATURE_ORDER is the single source of truth for the column order the scaler
and the classifier expect. Any model saved in ml/artifacts/ must be trained
with exactly this order and with class 1 meaning "default / not viable".

Protected attributes such as gender are deliberately not used as features.
"""
import os

# Numeric encoding of the categorical features.
CATEGORICAL_ENCODINGS = {
    "employment_status": {"employed": 0, "self_employed": 1, "retired": 2, "unemployed": 3},
    "payment_history": {"good": 0, "fair": 1, "poor": 2},
}

FEATURE_ORDER = [
    "age",
    "monthly_income",
    "employment_status",
    "years_employment",
    "credit_score",
    "existing_debt",
    "dti_ratio",
    "loan_amount",
    "loan_term",
    "previous_loans",
    "payment_history",
]

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
MODEL_PATH = os.path.join(ARTIFACTS_DIR, "credit_model.pkl")
SCALER_PATH = os.path.join(ARTIFACTS_DIR, "scaler.pkl")

# ---------------------------------------------------------------------------
# ML phase: feature sets for the models trained on the real dataset.
# FEATURE_ORDER above is unchanged: it still describes the form and the
# placeholder model. See docs/ML_PHASE.md.
# ---------------------------------------------------------------------------

EXAMPLE_ARTIFACTS_DIR = os.path.join(ARTIFACTS_DIR, "_example")
MANIFEST_FILENAME = "manifest.json"
METRICS_FILENAME = "metrics.json"
MODEL_FILENAME = "model.joblib"

PLACEHOLDER_FEATURE_SET = "v1-placeholder"
DEFAULT_FEATURE_SET = "v2-loan-default"

# feature set name -> columns the model receives, in order, and which of them are categorical.
FEATURE_SETS = {
    PLACEHOLDER_FEATURE_SET: {
        "columns": tuple(FEATURE_ORDER),
        "categorical": (),
    },
    # Built from 9 form fields. existing_debt and payment_history are still stored
    # with each application, but this feature set does not use them.
    DEFAULT_FEATURE_SET: {
        "columns": (
            "Age",
            "Income",
            "LoanAmount",
            "CreditScore",
            "MonthsEmployed",
            "NumCreditLines",
            "LoanTerm",
            "DTIRatio",
            "EmploymentType",
        ),
        "categorical": ("EmploymentType",),
    },
}

# Form value of employment_status -> EmploymentType category of the dataset.
# The dataset has no "Retired" category; retired applicants are mapped to Part-time.
EMPLOYMENT_TYPE_MAP = {
    "employed": "Full-time",
    "self_employed": "Self-employed",
    "unemployed": "Unemployed",
    "retired": "Part-time",
}

# Inclusive ranges observed in the dataset. Form values outside them are clipped
# so the model never sees values it was not trained on.
CLIP_RANGES = {
    "Age": (18, 69),
    "LoanTerm": (12, 60),
    "NumCreditLines": (1, 4),
    "CreditScore": (300, 849),
}


def to_model_frame(application, feature_set=DEFAULT_FEATURE_SET):
    """Turn one validated form application into the model input.

    Args:
        application: Form values keyed by form field name, as returned by
            ``app.credit.forms.validate_form`` (``age``, ``monthly_income``,
            ``employment_status``, ``years_employment``, ``credit_score``,
            ``dti_ratio``, ``loan_amount``, ``loan_term``, ``previous_loans``;
            ``existing_debt`` and ``payment_history`` are ignored).
        feature_set: A key of ``FEATURE_SETS``.

    Returns:
        A one-row ``pandas.DataFrame`` whose columns are exactly
        ``FEATURE_SETS[feature_set]["columns"]``, in that order.

    Mapping for ``v2-loan-default``:
        - age -> Age, clipped to ``CLIP_RANGES["Age"]``.
        - monthly_income * 12 -> Income (the dataset Income is annual).
        - employment_status -> EmploymentType through ``EMPLOYMENT_TYPE_MAP``.
          ``validate_form`` returns the encoded integer, so decode it with
          ``CATEGORICAL_ENCODINGS["employment_status"]`` first.
        - years_employment * 12 -> MonthsEmployed (rounded to an integer).
        - credit_score -> CreditScore, clipped to ``CLIP_RANGES["CreditScore"]``.
        - dti_ratio / 100 -> DTIRatio (the form uses percent, the dataset a ratio).
        - loan_amount -> LoanAmount.
        - loan_term -> LoanTerm, clipped to ``CLIP_RANGES["LoanTerm"]``.
        - previous_loans -> NumCreditLines, clipped to ``CLIP_RANGES["NumCreditLines"]``.

    Raises:
        ValueError: If ``feature_set`` is unknown or a required field is missing.
    """
    import pandas as pd

    if feature_set not in FEATURE_SETS:
        raise ValueError(f"Unknown feature set: {feature_set}")
    if feature_set != DEFAULT_FEATURE_SET:
        raise ValueError(f"to_model_frame only supports {DEFAULT_FEATURE_SET!r}")

    required = (
        "age", "monthly_income", "employment_status", "years_employment",
        "credit_score", "dti_ratio", "loan_amount", "loan_term", "previous_loans",
    )
    missing = [name for name in required if name not in application]
    if missing:
        raise ValueError(f"Missing form fields: {missing}")

    def clip(column, value):
        low, high = CLIP_RANGES[column]
        return min(max(value, low), high)

    status_by_code = {code: status for status, code in CATEGORICAL_ENCODINGS["employment_status"].items()}
    status = application["employment_status"]
    status = status_by_code.get(status, status)
    if status not in EMPLOYMENT_TYPE_MAP:
        raise ValueError(f"Unknown employment status: {status!r}")

    row = {
        "Age": clip("Age", application["age"]),
        # The dataset Income is annual (see data_report.json); the form is monthly.
        "Income": application["monthly_income"] * 12,
        "LoanAmount": application["loan_amount"],
        "CreditScore": clip("CreditScore", application["credit_score"]),
        "MonthsEmployed": int(round(application["years_employment"] * 12)),
        "NumCreditLines": clip("NumCreditLines", application["previous_loans"]),
        "LoanTerm": clip("LoanTerm", application["loan_term"]),
        "DTIRatio": application["dti_ratio"] / 100,
        "EmploymentType": EMPLOYMENT_TYPE_MAP[status],
    }
    columns = list(FEATURE_SETS[feature_set]["columns"])
    return pd.DataFrame([row], columns=columns)
