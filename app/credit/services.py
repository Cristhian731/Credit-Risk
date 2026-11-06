"""Credit viability prediction: loads the saved model and turns inputs into a decision.

The classifier must expose ``predict_proba`` with class 1 = "default / not viable".
"""
import logging
import os

import joblib
import numpy as np
from flask import current_app

from ml.features import FEATURE_ORDER

log = logging.getLogger(__name__)

RECOMMENDATIONS = {
    "Approved": "Low default risk. The application can proceed through the standard approval flow.",
    "Medium Risk": "Moderate default risk. Request additional guarantees or documents, or adjust the amount or term before approving.",
    "High Risk": "High default risk. Rejecting or restructuring the application is recommended.",
}


class PredictionService:
    """Wraps the scaler and classifier saved in ml/artifacts/."""

    def __init__(self, model_path, scaler_path, approved_max, medium_max):
        self.approved_max = approved_max
        self.medium_max = medium_max
        self.model = None
        self.scaler = None
        self._load(model_path, scaler_path)

    def _load(self, model_path, scaler_path):
        # Missing artifacts must not crash the app; the page shows a clear error instead.
        if not (os.path.exists(model_path) and os.path.exists(scaler_path)):
            log.warning("Credit model artifacts not found. Run: python -m ml.train_placeholder_model")
            return
        self.model = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)

    @property
    def is_ready(self):
        return self.model is not None and self.scaler is not None

    def classify(self, risk):
        """Map a default probability (0-1) to a decision label."""
        if risk < self.approved_max:
            return "Approved"
        if risk < self.medium_max:
            return "Medium Risk"
        return "High Risk"

    def predict(self, values):
        """Evaluate one application.

        Args:
            values: Encoded features keyed by name (see ml.features.FEATURE_ORDER).

        Returns:
            A dict with ``label``, ``risk_percent`` and ``recommendation``.

        Raises:
            RuntimeError: If the model artifacts could not be loaded.
        """
        if not self.is_ready:
            raise RuntimeError("The credit prediction model is not available.")

        x = np.array([[values[name] for name in FEATURE_ORDER]], dtype=float)
        risk = float(self.model.predict_proba(self.scaler.transform(x))[0][1])
        label = self.classify(risk)
        return {
            "label": label,
            "risk_percent": round(risk * 100, 1),
            "recommendation": RECOMMENDATIONS[label],
        }


def get_predictor():
    """Return the PredictionService created by create_app()."""
    return current_app.extensions["credit_predictor"]
