"""Credit viability prediction: loads the saved model and turns inputs into a decision.

The classifier must expose ``predict_proba`` with class 1 = "default / not viable".
"""
import logging
import os

import joblib
import numpy as np
from flask import current_app

from ml.features import FEATURE_ORDER, MANIFEST_FILENAME, METRICS_FILENAME
from ml.schemas import load_json

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


class ModelRegistry:
    """Access point to the trained models described by ``ml/artifacts/manifest.json``.

    Behaviour by phase (see docs/ML_PHASE.md):

    - Today (no ``manifest.json``): ``predict`` delegates to the placeholder
      ``PredictionService`` unchanged, and ``catalog`` serves the example
      metrics in ``ml/artifacts/_example`` so the model pages can be built.
    - Sprint 1: with a real manifest, ``predict(data)`` uses the champion.
      The model file is loaded lazily on the first prediction, never at
      start-up.
    - Sprint 2: ``predict(data, model=name)`` loads any of the three models
      on demand and keeps **at most one model in memory at a time**: loading
      another one releases the previous one (Render free plan: 512 MB).

    The model pages only read JSON, so they never load a model file.
    """

    def __init__(self, artifacts_dir, example_dir, fallback):
        """
        Args:
            artifacts_dir: Folder of the real artifacts (``ml.features.ARTIFACTS_DIR``).
            example_dir: Folder of the example artifacts (``ml.features.EXAMPLE_ARTIFACTS_DIR``).
            fallback: The placeholder ``PredictionService`` used while there is no manifest.
        """
        self.artifacts_dir = artifacts_dir
        self.example_dir = example_dir
        self.fallback = fallback
        # (model name, fitted pipeline) of the only model kept in memory, or None.
        self._loaded = None

    @property
    def has_trained_models(self):
        """True once ``ml/artifacts/manifest.json`` exists."""
        return os.path.exists(os.path.join(self.artifacts_dir, MANIFEST_FILENAME))

    @property
    def loaded_model(self):
        """Name of the model currently in memory, or None."""
        return self._loaded[0] if self._loaded else None

    def catalog(self):
        """Return the manifest and every model's metrics, for the model pages.

        Returns:
            ``{"manifest": dict, "metrics": {name: dict}, "is_example": bool}``.
            ``is_example`` is True while there are no trained models and the
            content comes from the example folder. Metrics follow
            ``manifest["models"]`` order.
        """
        is_example = not self.has_trained_models
        directory = self.example_dir if is_example else self.artifacts_dir
        manifest = load_json(os.path.join(directory, MANIFEST_FILENAME))
        metrics = {
            name: load_json(os.path.join(directory, name, METRICS_FILENAME))
            for name in manifest["models"]
        }
        return {"manifest": manifest, "metrics": metrics, "is_example": is_example}

    def predict(self, data, model=None):
        """Evaluate one application.

        Args:
            data: Encoded form values keyed by name, as returned by
                ``app.credit.forms.validate_form``.
            model: None for the official model (the champion), or one of
                ``ml.schemas.MODEL_NAMES`` (Sprint 2).

        Returns:
            Same shape as ``PredictionService.predict``: ``label``,
            ``risk_percent`` (risk score 0-100) and ``recommendation``.

        Raises:
            RuntimeError: If no model is available.
        """
        if model is None and not self.has_trained_models:
            return self.fallback.predict(data)
        raise NotImplementedError("Sprint 1 - owner: ml (trained models); Sprint 2 for model=<name>")


def get_predictor():
    """Return the PredictionService created by create_app()."""
    return current_app.extensions["credit_predictor"]


def get_registry():
    """Return the ModelRegistry created by create_app()."""
    return current_app.extensions["model_registry"]
