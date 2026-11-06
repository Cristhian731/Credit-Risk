"""Input definition and validation for the credit application form.

The fields follow ml.features.FEATURE_ORDER, which is also the display order.
"""
from ml.features import CATEGORICAL_ENCODINGS, FEATURE_ORDER

# field name -> (label, type, min, max, step)
NUMERIC_FIELDS = {
    "age": ("Age", int, 18, 100, 1),
    "monthly_income": ("Monthly Income", float, 0, 10_000_000, 0.01),
    "years_employment": ("Years of Employment", float, 0, 60, 0.1),
    "credit_score": ("Credit Score (300-850)", int, 300, 850, 1),
    "existing_debt": ("Existing Debt", float, 0, 100_000_000, 0.01),
    "dti_ratio": ("Debt-to-Income Ratio (%)", float, 0, 100, 0.1),
    "loan_amount": ("Loan Amount", float, 1, 100_000_000, 0.01),
    "loan_term": ("Loan Term (months)", int, 1, 480, 1),
    "previous_loans": ("Previous Loans", int, 0, 100, 1),
}

# field name -> (label, [(value, option text), ...]); values match CATEGORICAL_ENCODINGS.
CHOICE_FIELDS = {
    "employment_status": (
        "Employment Status",
        [("employed", "Employed"), ("self_employed", "Self-employed"),
         ("retired", "Retired"), ("unemployed", "Unemployed")],
    ),
    "payment_history": (
        "Payment History",
        [("good", "Good"), ("fair", "Fair"), ("poor", "Poor")],
    ),
}

FIELD_ORDER = FEATURE_ORDER


def validate_form(form):
    """Validate the submitted form.

    Args:
        form: A mapping such as ``request.form``.

    Returns:
        ``(clean_values, errors)``: typed and encoded values keyed by feature
        name, and a list of human-readable error messages.
    """
    clean, errors = {}, []

    for name, (label, cast, low, high, _step) in NUMERIC_FIELDS.items():
        raw = (form.get(name) or "").strip()
        try:
            value = cast(raw)
        except ValueError:
            errors.append(f"{label} must be a valid number.")
            continue
        if not low <= value <= high:
            errors.append(f"{label} must be between {low} and {high}.")
            continue
        clean[name] = value

    for name, (label, _options) in CHOICE_FIELDS.items():
        raw = (form.get(name) or "").strip().lower()
        encoding = CATEGORICAL_ENCODINGS[name]
        if raw not in encoding:
            errors.append(f"{label} has an invalid value.")
            continue
        clean[name] = encoding[raw]

    return clean, errors


def to_record(values):
    """Return validated values with the choice fields as text, ready to be saved.

    The model receives numeric codes, but the stored application keeps the
    readable values (e.g. "employed") used by the form and app/models.py.
    """
    record = dict(values)
    for name in CHOICE_FIELDS:
        codes = {code: text for text, code in CATEGORICAL_ENCODINGS[name].items()}
        record[name] = codes[values[name]]
    return record
