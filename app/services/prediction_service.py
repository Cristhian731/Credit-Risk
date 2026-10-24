"""Model layer: loads the scaler + classifier and turns inputs into a decision.

The classifier must expose predict_proba, with class 1 = "default / not viable".
"""
import logging
import os

import joblib
import numpy as np

from ..forms import FEATURE_ORDER

log = logging.getLogger(__name__)

RECOMMENDATIONS = {
    "Approved": "Low default risk. The application can proceed through the standard approval flow.",
    "Medium Risk": "Moderate default risk. Request additional guarantees or documents, or adjust amount/term before approving.",
    "High Risk": "High default risk. Rejecting or restructuring the application is recommended.",
}


class PredictionService:
    def __init__(self, model_path, scaler_path, approved_max, medium_max):
        self.approved_max = approved_max
        self.medium_max = medium_max
        self.model = None
        self.scaler = None
        self._load(model_path, scaler_path)

    def _load(self, model_path, scaler_path):
        # Missing artifacts must not crash the app; the UI shows a clear error instead.
        if not (os.path.exists(model_path) and os.path.exists(scaler_path)):
            log.warning("Model artifacts not found. Run scripts/train_placeholder_model.py")
            return
        self.model = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)

    @property
    def is_ready(self):
        return self.model is not None and self.scaler is not None

    def predict(self, values):
        """values: dict of encoded features. Returns a result dict for the view."""
        if not self.is_ready:
            raise RuntimeError("The prediction model is not available.")

        x = np.array([[values[name] for name in FEATURE_ORDER]], dtype=float)
        risk = float(self.model.predict_proba(self.scaler.transform(x))[0][1])

        if risk < self.approved_max:
            label = "Approved"
        elif risk < self.medium_max:
            label = "Medium Risk"
        else:
            label = "High Risk"

        return {
            "label": label,
            "risk_percent": round(risk * 100, 1),
            "recommendation": RECOMMENDATIONS[label],
        }
