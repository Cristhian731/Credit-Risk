"""Configuration classes, selected by name in ``app.create_app()``."""
import os

from ml.features import MODEL_PATH, SCALER_PATH


LOCAL_DATABASE_URL = "sqlite:///credit_risk.db"

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
# Password of the demo account (flask seed-demo and the Methodology overview). Development and tests
# have a default; production must set DEMO_PASSWORD in the environment.
DEFAULT_DEMO_PASSWORD = "demo-password-2026"

# Plain scheme -> SQLAlchemy scheme with the driver listed in requirements.txt.
_DATABASE_DRIVERS = {
    "postgres://": "postgresql+psycopg://",
    "postgresql://": "postgresql+psycopg://",
    "mysql://": "mysql+pymysql://",
}


def _env_flag(name, default):
    """Read a boolean environment variable ("true"/"1"/"yes"/"on" mean True)."""
    return os.environ.get(name, str(default)).strip().lower() in ("true", "1", "yes", "on")


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

    PROJECT_ROOT = PROJECT_ROOT
    SECRET_KEY = os.environ.get("SECRET_KEY")
    DEBUG = False
    TESTING = False

    # Relative SQLite paths are stored in the Flask instance/ folder.
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Authentication switch (see app/auth/services.py and README.md).
    # False: every request runs as the persisted demo user (flask seed-demo).
    # True: the real authentication is used.
    AUTH_ENABLED = _env_flag("AUTH_ENABLED", False)

    # CSRF protection for every POST form. The token is tied to the session, so
    # it does not expire on its own (a form left open for hours still works).
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # Session cookie: unreadable from JavaScript and not sent on cross-site
    # requests. SECURE (HTTPS only) is turned on in production.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False

    # Rows per page in the transaction list and the evaluation history.
    PAGE_SIZE = 20

    # Logging: LOG_LEVEL (default INFO) and an optional rotating LOG_FILE.
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE = os.environ.get("LOG_FILE") or None

    # Credit viability model saved by the ml/ package.
    CREDIT_MODEL_PATH = os.environ.get("CREDIT_MODEL_PATH", MODEL_PATH)
    CREDIT_SCALER_PATH = os.environ.get("CREDIT_SCALER_PATH", SCALER_PATH)
    # Default-probability cut-offs: below the first is "Approved", below the
    # second is "Medium Risk", anything else is "High Risk".
    CREDIT_APPROVED_MAX_RISK = 0.33
    CREDIT_MEDIUM_MAX_RISK = 0.66

    # Demo account password (public on purpose: the demo holds no real data). No default here.
    DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD") or None

    # Prediction log (JSON lines, one per prediction, no customer name or document). An empty
    # value turns it off. The file is ignored by git. Entries older than the retention are purged
    # with: flask --app run purge-prediction-log
    PREDICTION_LOG_PATH = os.environ.get("PREDICTION_LOG_PATH", os.path.join(PROJECT_ROOT, "logs", "predictions.jsonl"))
    PREDICTION_LOG_RETENTION_DAYS = int(os.environ.get("PREDICTION_LOG_RETENTION_DAYS", "90"))

    # Review of the models by a domain expert, shown in the Methodology (Phase 4).
    EXPERT_REVIEW_PATH = os.path.join(PROJECT_ROOT, "docs", "expert_review.md")


class DevelopmentConfig(Config):
    DEBUG = True
    # Real authentication by default in development (and production); testing keeps the base value.
    AUTH_ENABLED = _env_flag("AUTH_ENABLED", True)
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
    DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD") or DEFAULT_DEMO_PASSWORD


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-only-insecure-key"
    # In-memory SQLite by default; CI sets TEST_DATABASE_URL to run the same tests on PostgreSQL.
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.environ.get("TEST_DATABASE_URL", "").strip()) or "sqlite:///:memory:"
    AUTH_ENABLED = False
    # Tests post forms directly; tests/test_csrf.py turns the protection on.
    WTF_CSRF_ENABLED = False
    DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD") or DEFAULT_DEMO_PASSWORD
    # The prediction log is off in tests unless a test turns it on with a temporary path.
    PREDICTION_LOG_PATH = ""


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    # Real authentication by default: demo mode must never hold real data.
    AUTH_ENABLED = _env_flag("AUTH_ENABLED", True)
    # SECRET_KEY must come from the environment; create_app() refuses to start without it.


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
