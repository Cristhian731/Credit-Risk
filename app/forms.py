"""Input schema and validation for the customer form.

FEATURE_ORDER is the single source of truth for the column order expected by
the scaler/model. The training script must use the same order.
"""

# field name -> (label, type, min, max)
NUMERIC_FIELDS = {
    "age": ("Age", int, 18, 100),
    "monthly_income": ("Monthly Income", float, 0, 10_000_000),
    "years_employment": ("Years of Employment", float, 0, 60),
    "credit_score": ("Credit Score", int, 300, 850),
    "existing_debt": ("Existing Debt", float, 0, 100_000_000),
    "dti_ratio": ("Debt-to-Income Ratio (%)", float, 0, 100),
    "loan_amount": ("Loan Amount", float, 1, 100_000_000),
    "loan_term": ("Loan Term (months)", int, 1, 480),
    "previous_loans": ("Previous Loans", int, 0, 100),
}

# Categorical fields and their numeric encoding (shared with training).
CATEGORICAL_FIELDS = {
    "gender": {"female": 0, "male": 1, "other": 2},
    "employment_status": {"employed": 0, "self_employed": 1, "retired": 2, "unemployed": 3},
    "payment_history": {"good": 0, "fair": 1, "poor": 2},
}

FEATURE_ORDER = [
    "age", "gender", "monthly_income", "employment_status", "years_employment",
    "credit_score", "existing_debt", "dti_ratio", "loan_amount", "loan_term",
    "previous_loans", "payment_history",
]


def validate_form(form):
    """Return (clean_values, errors). clean_values holds typed, encoded data."""
    clean, errors = {}, []

    for name, (label, cast, lo, hi) in NUMERIC_FIELDS.items():
        raw = (form.get(name) or "").strip()
        try:
            value = cast(raw)
        except ValueError:
            errors.append(f"{label} must be a valid number.")
            continue
        if not lo <= value <= hi:
            errors.append(f"{label} must be between {lo} and {hi}.")
            continue
        clean[name] = value

    for name, mapping in CATEGORICAL_FIELDS.items():
        raw = (form.get(name) or "").strip().lower()
        if raw not in mapping:
            errors.append(f"{name.replace('_', ' ').title()} has an invalid value.")
            continue
        clean[name] = mapping[raw]

    return clean, errors
