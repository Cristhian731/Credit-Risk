"""Credit viability prediction: loads the saved model and turns inputs into a decision.

The classifier must expose ``predict_proba`` with class 1 = "default / not viable".
"""
import gc
import logging
import os
import threading

import joblib
import numpy as np
from flask import current_app

from .prediction_log import PredictionLog
from ml.features import FEATURE_ORDER, MANIFEST_FILENAME, METRICS_FILENAME, MODEL_FILENAME, to_model_frame
from ml.schemas import CHAMPION_AUC_MARGIN, MODEL_NAMES, load_json, model_version_tag

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

    - Without ``manifest.json``: ``predict`` delegates to the placeholder
      ``PredictionService`` unchanged, and ``catalog`` serves the example
      metrics in ``ml/artifacts/_example`` so the model pages can be built.
    - With a real manifest: ``predict(data)`` uses the champion and
      ``predict(data, model=name)`` any of the three models. A model file is
      loaded on demand, never at start-up, and **at most one model stays in
      memory**: loading another one releases the previous one (Render free
      plan: 512 MB).

    The model pages only read JSON, so they never load a model file.
    """

    def __init__(self, artifacts_dir, example_dir, fallback, prediction_log=None):
        """
        Args:
            artifacts_dir: Folder of the real artifacts (``ml.features.ARTIFACTS_DIR``).
            example_dir: Folder of the example artifacts (``ml.features.EXAMPLE_ARTIFACTS_DIR``).
            fallback: The placeholder ``PredictionService`` used while there is no manifest.
            prediction_log: ``PredictionLog`` that records every prediction of a trained model
                (default: none).
        """
        self.artifacts_dir = artifacts_dir
        self.example_dir = example_dir
        self.fallback = fallback
        self.prediction_log = prediction_log or PredictionLog("")
        # (model name, fitted pipeline, artifact version) of the only model kept in memory, or None.
        self._loaded = None
        self._lock = threading.Lock()

    @property
    def has_trained_models(self):
        """True once ``ml/artifacts/manifest.json`` exists."""
        return os.path.exists(os.path.join(self.artifacts_dir, MANIFEST_FILENAME))

    @property
    def loaded_model(self):
        """Name of the model currently in memory, or None."""
        return self._loaded[0] if self._loaded else None

    def _read(self, directory, filename):
        path = os.path.join(directory, filename)
        return load_json(path) if os.path.exists(path) else None

    def artifact(self, filename):
        """Content of a JSON file of the real artifacts folder (never the example one), or None if it does not exist."""
        return self._read(self.artifacts_dir, filename)

    def catalog(self):
        """Return the manifest and every model's metrics, for the model pages.

        Returns:
            ``{"manifest", "metrics", "is_example", "experiments", "overfitting"}``.
            ``is_example`` is True while there are no trained models and the
            content comes from the example folder. Metrics follow
            ``manifest["models"]`` order. ``experiments`` (every hyperparameter
            run) and ``overfitting`` (train vs. CV vs. test) are the content of
            their JSON files, or None when the folder does not have them.
        """
        is_example = not self.has_trained_models
        directory = self.example_dir if is_example else self.artifacts_dir
        manifest = load_json(os.path.join(directory, MANIFEST_FILENAME))
        metrics = {
            name: load_json(os.path.join(directory, name, METRICS_FILENAME))
            for name in manifest["models"]
        }
        return {
            "manifest": manifest,
            "metrics": metrics,
            "is_example": is_example,
            "experiments": self._read(directory, "experiments.json"),
            "overfitting": self._read(directory, "overfitting.json"),
        }

    def selection_summary(self, catalog=None):
        """Explain the champion rule with the numbers of the catalog (for the comparison page).

        Returns:
            One dict per model, in catalog order: ``name``, ``display_name``,
            ``cv_roc_auc``, ``gap`` (distance to the best CV ROC AUC), ``tied`` (closer than
            ``CHAMPION_AUC_MARGIN``), ``cv_recall`` and ``is_champion``.
        """
        catalog = catalog or self.catalog()
        auc = {name: m["cv"]["roc_auc"][0] for name, m in catalog["metrics"].items()}
        best = max(auc.values())
        return [
            {
                "name": name,
                "display_name": m["display_name"],
                "cv_roc_auc": auc[name],
                "gap": best - auc[name],
                "tied": best - auc[name] < CHAMPION_AUC_MARGIN,
                "cv_recall": m["cv"]["recall"][0],
                "is_champion": name == catalog["manifest"]["champion"],
            }
            for name, m in catalog["metrics"].items()
        ]

    def _model(self, name):
        """Return ``(pipeline, artifact version)`` of a model, loading it if it is not the one in memory."""
        with self._lock:
            if self._loaded and self._loaded[0] == name:
                return self._loaded[1], self._loaded[2]
            path = os.path.join(self.artifacts_dir, name, MODEL_FILENAME)
            if not os.path.exists(path):
                raise RuntimeError(f"The model file of {name} is not available.")
            version = load_json(os.path.join(self.artifacts_dir, MANIFEST_FILENAME))["version"]
            self._loaded = None  # release the previous model before loading the next one
            gc.collect()
            self._loaded = (name, joblib.load(path), version)
            return self._loaded[1], self._loaded[2]

    def predict(self, data, model=None):
        """Evaluate one application.

        Args:
            data: Encoded form values keyed by name, as returned by
                ``app.credit.forms.validate_form``.
            model: None for the official model (the champion), or one of
                ``ml.schemas.MODEL_NAMES``.

        Returns:
            Same shape as ``PredictionService.predict``: ``label``,
            ``risk_percent`` (risk score 0-100) and ``recommendation``. With trained
            models it also has ``model`` (name) and ``model_version`` in the
            ``<code>@<version>`` format that is stored with the evaluation.

        Raises:
            RuntimeError: If no model is available.
            ValueError: If ``model`` is not one of the model names.
        """
        if model is not None and model not in MODEL_NAMES:
            raise ValueError(f"Unknown model: {model}")
        if model is None and not self.has_trained_models:
            return self.fallback.predict(data)
        if not self.has_trained_models:
            raise RuntimeError("The trained models are not available.")

        name = model or load_json(os.path.join(self.artifacts_dir, MANIFEST_FILENAME))["champion"]
        pipeline, version = self._model(name)
        frame = to_model_frame(data)
        risk = float(pipeline.predict_proba(frame)[0][1])
        label = self.fallback.classify(risk)
        tag = model_version_tag(name, version)
        # Monitoring: the model inputs, never the customer name or document.
        self.prediction_log.record(name, tag, frame.iloc[0].to_dict(), risk, label)
        return {
            "label": label,
            "risk_percent": round(risk * 100, 1),
            "recommendation": RECOMMENDATIONS[label],
            "model": name,
            "model_version": tag,
        }


def get_predictor():
    """Return the PredictionService created by create_app()."""
    return current_app.extensions["credit_predictor"]


def get_registry():
    """Return the ModelRegistry created by create_app()."""
    return current_app.extensions["model_registry"]
