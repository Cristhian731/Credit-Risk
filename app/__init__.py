"""Application factory: builds the Flask app and wires its components."""
from flask import Flask

from .config import Config
from .routes import main_bp
from .services.prediction_service import PredictionService


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # One shared service instance: the model is loaded once, not per request.
    app.extensions["prediction_service"] = PredictionService(
        model_path=app.config["MODEL_PATH"],
        scaler_path=app.config["SCALER_PATH"],
        approved_max=app.config["APPROVED_MAX_RISK"],
        medium_max=app.config["MEDIUM_MAX_RISK"],
    )

    app.register_blueprint(main_bp)
    return app
