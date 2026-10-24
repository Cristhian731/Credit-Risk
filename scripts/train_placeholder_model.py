"""Generates PLACEHOLDER credit_model.pkl and scaler.pkl from synthetic data.

Only for wiring/testing the app. Replace with the real CRISP-DM pipeline,
keeping the same feature order (app.forms.FEATURE_ORDER) and class 1 = default.
Usage: python scripts/train_placeholder_model.py
"""
import os
import sys

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from app.forms import FEATURE_ORDER  # noqa: E402

rng = np.random.default_rng(42)
n = 3000
data = {
    "age": rng.integers(18, 75, n),
    "gender": rng.integers(0, 3, n),
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
X = np.column_stack([data[f] for f in FEATURE_ORDER]).astype(float)

# Synthetic default probability driven by score, DTI, payment history, employment.
logit = (-0.012 * (data["credit_score"] - 600) + 0.05 * (data["dti_ratio"] - 30)
         + 0.8 * data["payment_history"] + 0.6 * (data["employment_status"] == 3) - 0.3)
y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)

scaler = StandardScaler().fit(X)
model = LogisticRegression(max_iter=1000).fit(scaler.transform(X), y)

out = os.path.join(ROOT, "models")
os.makedirs(out, exist_ok=True)
joblib.dump(model, os.path.join(out, "credit_model.pkl"))
joblib.dump(scaler, os.path.join(out, "scaler.pkl"))
print("Saved placeholder credit_model.pkl and scaler.pkl in", out)
