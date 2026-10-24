"""Central configuration (paths, secrets, risk thresholds)."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    # Override SECRET_KEY via environment variable in production.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    # Serialized artifacts produced by the training pipeline.
    MODEL_PATH = os.path.join(BASE_DIR, "models", "credit_model.pkl")
    SCALER_PATH = os.path.join(BASE_DIR, "models", "scaler.pkl")

    # Default-probability cut-offs used to build the risk category.
    APPROVED_MAX_RISK = 0.33
    MEDIUM_MAX_RISK = 0.66
