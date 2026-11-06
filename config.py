"""Configuration classes, selected by name in ``app.create_app()``."""
import os

from ml.features import MODEL_PATH, SCALER_PATH


LOCAL_DATABASE_URL = "sqlite:///credit_risk.db"

# Plain scheme -> SQLAlchemy scheme with the driver listed in requirements.txt.
_DATABASE_DRIVERS = {
    "postgres://": "postgresql+psycopg://",
    "postgresql://": "postgresql+psycopg://",
    "mysql://": "mysql+pymysql://",
}


def _env_flag(name, default):
    """Read a boolean environment variable ("true"/"false")."""
    return os.environ.get(name, str(default)).strip().lower() == "true"


def normalize_database_url(url):
    """Add the installed driver to plain PostgreSQL and MySQL URLs.

    ``postgres://`` and ``postgresql://`` use psycopg, ``mysql://`` uses PyMySQL.
    URLs that already name a driver, and SQLite URLs, are returned unchanged.
    """
    for prefix, replacement in _DATABASE_DRIVERS.items():
        if url.startswith(prefix):
            return replacement + url[len(prefix):]
    return url


def database_url():
    """Return the database URL from DATABASE_URL, or a local SQLite file.

    Credentials belong in the environment variable, never in the code:
        postgresql://user:password@host:5432/credit_risk
        mysql://user:password@host:3306/credit_risk
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    return normalize_database_url(url) if url else LOCAL_DATABASE_URL


class Config:
    """Settings shared by every environment."""

    SECRET_KEY = os.environ.get("SECRET_KEY")
    DEBUG = False
    TESTING = False

    # Relative SQLite paths are stored in the Flask instance/ folder.
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Authentication switch (see app/auth/services.py and README.md).
    # False: login_required lets every request through and get_current_user()
    # returns a demo user (id=1). True: the real authentication is used.
    AUTH_ENABLED = _env_flag("AUTH_ENABLED", False)

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


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-only-insecure-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    AUTH_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    # SECRET_KEY must come from the environment; create_app() refuses to start without it.


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
