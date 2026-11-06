"""Configuration classes, selected by name in ``app.create_app()``."""
import os

from ml.features import MODEL_PATH, SCALER_PATH


def _env_flag(name, default):
    """Read a boolean environment variable ("true"/"false")."""
    return os.environ.get(name, str(default)).strip().lower() == "true"


class Config:
    """Settings shared by every environment."""

    SECRET_KEY = os.environ.get("SECRET_KEY")
    DEBUG = False
    TESTING = False

    # Relative SQLite paths are stored in the Flask instance/ folder.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///credit_risk.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # When True, app/auth/services.py answers with a fake user so the rest of
    # the app can be built before real authentication exists.
    FAKE_AUTH = _env_flag("FAKE_AUTH", False)

    # Credit viability model saved by the ml/ package.
    CREDIT_MODEL_PATH = os.environ.get("CREDIT_MODEL_PATH", MODEL_PATH)
    CREDIT_SCALER_PATH = os.environ.get("CREDIT_SCALER_PATH", SCALER_PATH)
    # Default-probability cut-offs: below the first is "Approved", below the
    # second is "Medium Risk", anything else is "High Risk".
    CREDIT_APPROVED_MAX_RISK = 0.33
    CREDIT_MEDIUM_MAX_RISK = 0.66


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
    FAKE_AUTH = _env_flag("FAKE_AUTH", True)


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-only-insecure-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    FAKE_AUTH = False


class ProductionConfig(Config):
    DEBUG = False
    # SECRET_KEY must come from the environment; create_app() refuses to start without it.
    FAKE_AUTH = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
