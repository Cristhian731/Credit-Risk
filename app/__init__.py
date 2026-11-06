"""Credit Risk application package."""
import os

from flask import Flask

from config import config_by_name

from .auth.services import auth_enabled, get_current_user
from .credit.services import PredictionService
from .extensions import db

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def create_app(config_name=None):
    """Build and configure a Flask application.

    Args:
        config_name: "development", "testing" or "production". Defaults to the
            FLASK_CONFIG environment variable, or "development" if it is unset.

    Returns:
        A configured Flask application.
    """
    config_name = config_name or os.environ.get("FLASK_CONFIG", "development")
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, "templates"),
        static_folder=os.path.join(PROJECT_ROOT, "static"),
    )
    app.config.from_object(config_by_name[config_name])

    if not app.config["SECRET_KEY"]:
        raise RuntimeError(
            f"SECRET_KEY environment variable is required for the '{config_name}' configuration."
        )

    db.init_app(app)

    # One shared instance: the model is loaded once, not per request.
    app.extensions["credit_predictor"] = PredictionService(
        model_path=app.config["CREDIT_MODEL_PATH"],
        scaler_path=app.config["CREDIT_SCALER_PATH"],
        approved_max=app.config["CREDIT_APPROVED_MAX_RISK"],
        medium_max=app.config["CREDIT_MEDIUM_MAX_RISK"],
    )

    register_blueprints(app)

    @app.context_processor
    def inject_auth_state():
        # Available in every template: current_user and auth_enabled.
        return {"current_user": get_current_user(), "auth_enabled": auth_enabled()}

    return app


def register_blueprints(app):
    """Attach every feature blueprint to the application."""
    from .auth import bp as auth_bp
    from .credit import bp as credit_bp
    from .dashboard import bp as dashboard_bp
    from .main import bp as main_bp
    from .transactions import bp as transactions_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(credit_bp)
    app.register_blueprint(auth_bp)
