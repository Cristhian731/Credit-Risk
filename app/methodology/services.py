"""Data of the Methodology pages.

Every figure on those pages is read from the JSON files that the training and the monitoring write in
``ml/artifacts/``: nothing is typed in the templates. A file that does not exist is None and the page
says that it is not available yet.
"""
import os
import re

from flask import current_app

from ml.features import CLIP_RANGES, DEFAULT_FEATURE_SET, FEATURE_SETS
from ml.schemas import DISPLAY_NAMES, MODEL_CODES, MODEL_NAMES

REPOSITORY_URL = "https://github.com/Cristhian731/Credit-Risk"
COLAB_URL = (
    "https://colab.research.google.com/github/Cristhian731/Credit-Risk/blob/main/"
    "notebooks/credit_risk_dimensionality.ipynb"
)
KAGGLE_URL = "https://www.kaggle.com/datasets/nikhil1e9/loan-default"
TEAM = ("Cristhian Stiven Aza Diaz", "Harrison Camargo", "Alejandro Alarcon")

# (number, title) of the six CRISP-ML phases; the title is shown on the page and in the menu.
PHASES = (
    (1, "Business and Data Understanding"),
    (2, "Data Engineering"),
    (3, "Model Engineering"),
    (4, "Model Evaluation"),
    (5, "Deployment"),
    (6, "Monitoring and Maintenance"),
)

# Packages listed in the deployment phase (pinned versions are read from requirements.txt).
KEY_PACKAGES = ("Flask", "SQLAlchemy", "scikit-learn", "xgboost-cpu", "pandas", "numpy", "joblib", "gunicorn")


def load_artifacts():
    """Everything the pages read: the catalog of the registry plus the optional JSON reports."""
    registry = current_app.extensions["model_registry"]
    catalog = registry.catalog()
    artifacts = {
        "is_example": catalog["is_example"],
        "manifest": catalog["manifest"],
        "metrics": catalog["metrics"],
        "experiments": catalog["experiments"],
        "overfitting": catalog["overfitting"],
        "selection": registry.selection_summary(catalog),
    }
    for key, filename in (
        ("data_report", "data_report.json"),
        ("subgroups", "subgroups.json"),
        ("dimensionality", "dimensionality_report.json"),
        ("monitoring", "monitoring_report.json"),
        ("reference", "reference_distribution.json"),
    ):
        artifacts[key] = None if catalog["is_example"] else registry.artifact(filename)
    return artifacts


def derive(artifacts):
    """Values computed from the artifacts (not typed anywhere)."""
    manifest = artifacts["manifest"]
    champion = manifest["champion"]
    derived = {
        "champion": champion,
        "champion_display": DISPLAY_NAMES[champion],
        "champion_code": MODEL_CODES[champion],
        "model_features": list(FEATURE_SETS[manifest["feature_set"]]["columns"]),
        "n_model_features": len(FEATURE_SETS[manifest["feature_set"]]["columns"]),
        "clip_ranges": CLIP_RANGES,
        "display_names": DISPLAY_NAMES,
        "model_codes": MODEL_CODES,
    }
    report = artifacts["data_report"]
    if report:
        before = report["before"]
        inconsistent = before["inconsistencies"].get("months_employed_exceed_adult_life", 0)
        derived.update({
            "inconsistent_rows": inconsistent,
            "inconsistent_percent": 100 * inconsistent / before["rows"],
            "no_outliers": all(item["outliers"] == 0 for item in before["outliers"].values()),
            "defaults": round(before["rows"] * before["default_rate"]),
            "n_predictors": before["columns"] - 2,
        })
        derived["n_unused_predictors"] = derived["n_predictors"] - derived["n_model_features"]
    subgroups = artifacts["subgroups"]
    if subgroups:
        ages = subgroups["models"][champion]["age_range"]
        labels = list(ages)
        derived["age_ratio"] = ages[labels[0]]["predicted_default_rate"] / ages[labels[-1]]["predicted_default_rate"]
    return derived


def dependencies():
    """Pinned versions of the key packages, read from requirements.txt."""
    path = os.path.join(current_app.config["PROJECT_ROOT"], "requirements.txt")
    pins = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                match = re.match(r"([A-Za-z0-9_.\-]+)==([0-9][^\s;]*)", line.strip())
                if match:
                    pins.setdefault(match.group(1), match.group(2))
    except OSError:
        return []
    return [(name, pins[name]) for name in KEY_PACKAGES if name in pins]


def expert_review():
    """The review of the domain expert (docs/expert_review.md).

    The file starts with a header between ``---`` lines (``status``, ``name``, ``role``, ``organization``,
    ``date``). The review is complete only when ``status`` is ``complete`` and the name and the date are
    filled in. With ``status: not_conducted`` the page states that no review took place and shows the
    questionnaire as the validation protocol; with any other status it says "Pending".
    """
    path = current_app.config["EXPERT_REVIEW_PATH"]
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return {"complete": False, "not_conducted": False, "fields": {}, "body": "", "found": False}
    fields, body = {}, text
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if match:
        for line in match.group(1).splitlines():
            key, _, value = line.partition(":")
            fields[key.strip().lower()] = value.strip()
        body = text[match.end():]
    complete = fields.get("status", "").lower() == "complete" and bool(fields.get("name")) and bool(fields.get("date"))
    not_conducted = fields.get("status", "").lower() == "not_conducted"
    return {"complete": complete, "not_conducted": not_conducted, "fields": fields, "body": body.strip(), "found": True}


def demo_credentials():
    """E-mail and password of the demo account (the password is None if DEMO_PASSWORD is not configured)."""
    from ..auth.services import DEMO_EMAIL

    return {"email": DEMO_EMAIL, "password": current_app.config.get("DEMO_PASSWORD")}
