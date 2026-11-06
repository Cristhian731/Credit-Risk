"""Train a PLACEHOLDER credit model on synthetic data.

The output only exists so the web app can be built and demonstrated before
the real CRISP-DM pipeline is ready. Replace it with a model trained on real
data, keeping ml.features.FEATURE_ORDER and class 1 = default.

Usage (from the project root): python -m ml.train_placeholder_model
"""
import os

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from ml.features import ARTIFACTS_DIR, FEATURE_ORDER, MODEL_PATH, SCALER_PATH

SEED = 42
N_SAMPLES = 3000


def make_synthetic_data(rng, n):
    """Return (X, y) with plausible but fictitious customers."""
    data = {
        "age": rng.integers(18, 75, n),
        "monthly_income": rng.uniform(500, 15000, n),
        "employment_status": rng.integers(0, 4, n),
        "years_employment": rng.uniform(0, 30, n),
        "credit_score": rng.integers(300, 851, n),
        "existing_debt": rng.uniform(0, 50000, n),
        "dti_ratio": rng.uniform(0, 80, n),
        "loan_amount": rng.uniform(1000, 80000, n),
        "loan_term": rng.integers(6, 120, n),
        "previous_loans": rng.integers(0, 10, n),
        "payment_history": rng.integers(0, 3, n),
    }
    X = np.column_stack([data[name] for name in FEATURE_ORDER]).astype(float)

    # Default probability driven by score, DTI, payment history and unemployment.
    logit = (
        -0.012 * (data["credit_score"] - 600)
        + 0.05 * (data["dti_ratio"] - 30)
        + 0.8 * data["payment_history"]
        + 0.6 * (data["employment_status"] == 3)
        - 0.3
    )
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return X, y


def main():
    X, y = make_synthetic_data(np.random.default_rng(SEED), N_SAMPLES)
    scaler = StandardScaler().fit(X)
    model = LogisticRegression(max_iter=1000).fit(scaler.transform(X), y)

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"Saved placeholder model and scaler in {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
