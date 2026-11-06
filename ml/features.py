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
