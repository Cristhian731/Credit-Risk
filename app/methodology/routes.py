"""Methodology routes: public pages (no login), visible with and without a session."""
from flask import abort, current_app, render_template, request

from ml.schemas import PSI_ALERT, PSI_STABLE

from ..credit.forms import CHOICE_FIELDS, FIELD_ORDER, NUMERIC_FIELDS
from . import bp
from .services import (
    COLAB_URL,
    KAGGLE_URL,
    MODEL_NAMES,
    PHASES,
    REPOSITORY_URL,
    TEAM,
    demo_credentials,
    dependencies,
    derive,
    expert_review,
    load_artifacts,
)

# Retraining rule of Phase 6: retrain if the ROC AUC falls more than this below the validated value.
RETRAIN_AUC_DROP = 0.03


@bp.app_context_processor
def inject_phases():
    """The phases are available in every template (the Methodology menu of the navbar)."""
    return {"methodology_phases": PHASES}


def _context(**extra):
    artifacts = load_artifacts()
    return {
        "a": artifacts,
        "d": derive(artifacts),
        "phases": PHASES,
        "model_names": MODEL_NAMES,
        "repository_url": REPOSITORY_URL,
        "colab_url": COLAB_URL,
        "kaggle_url": KAGGLE_URL,
        "team": TEAM,
        **extra,
    }


@bp.route("/")
def overview():
    """Project overview: problem, objective, team, headline results, links and the demo account."""
    return render_template(
        "methodology/overview.html", **_context(demo=demo_credentials(), app_url=request.host_url, active_phase=0)
    )


@bp.route("/phase-<int:number>")
def phase(number):
    """One CRISP-ML phase. Numbers outside 1-6 answer 404."""
    if number not in dict(PHASES):
        abort(404)
    extra = {"active_phase": number, "title": dict(PHASES)[number]}
    if number == 4:
        extra["expert"] = expert_review()
    if number == 5:
        extra.update(
            packages=dependencies(),
            numeric_fields=NUMERIC_FIELDS,
            choice_fields=CHOICE_FIELDS,
            field_order=FIELD_ORDER,
            app_url=request.host_url,
            demo=demo_credentials(),
            thresholds={
                "approved": current_app.config["CREDIT_APPROVED_MAX_RISK"],
                "medium": current_app.config["CREDIT_MEDIUM_MAX_RISK"],
            },
        )
    if number == 6:
        extra.update(
            log=current_app.extensions["prediction_log"].summary(),
            retention_days=current_app.config["PREDICTION_LOG_RETENTION_DAYS"],
            psi_thresholds={"stable": PSI_STABLE, "alert": PSI_ALERT},
            retrain_auc_drop=RETRAIN_AUC_DROP,
        )
    return render_template(f"methodology/phase{number}.html", **_context(**extra))
