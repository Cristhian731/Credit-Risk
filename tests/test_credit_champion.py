"""The credit evaluation with the champion: sanity checks, model_version and the label distribution."""
import os
import warnings

import pytest

from app.credit.services import ModelRegistry
from app.models import CreditApplication
from app.services import repository
from ml.features import ARTIFACTS_DIR, EXAMPLE_ARTIFACTS_DIR, MANIFEST_FILENAME
from ml.schemas import (
    DISPLAY_NAMES,
    MODEL_CODES,
    MODEL_NAMES,
    load_json,
    model_version_tag,
    parse_model_version_tag,
)

pytestmark = pytest.mark.usefixtures("demo_user")

CLIENT = {"client_full_name": "Maria Lopez", "client_document": "100200300"}
# A clearly good applicant: mature, high stable income, excellent score, small short loan.
GOOD = {
    "age": "60", "monthly_income": "12000", "employment_status": "employed", "years_employment": "20",
    "credit_score": "800", "existing_debt": "0", "dti_ratio": "10", "loan_amount": "5000",
    "loan_term": "12", "previous_loans": "1", "payment_history": "good",
}
# A clearly bad applicant: young, low income, unemployed, poor score, large long loan.
BAD = {
    "age": "19", "monthly_income": "1500", "employment_status": "unemployed", "years_employment": "0",
    "credit_score": "350", "existing_debt": "5000", "dti_ratio": "85", "loan_amount": "90000",
    "loan_term": "60", "previous_loans": "4", "payment_history": "poor",
}
DATASET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml", "data", "raw", "Loan_default.csv")


@pytest.fixture
def credit_client(client):
    return client


def _evaluate(client, profile):
    response = client.post("/credit/", data={**CLIENT, **profile})
    assert response.status_code == 302
    return response.headers["Location"]


# Sanity check: the champion separates a clearly good profile from a clearly bad one

def test_clearly_good_profile_is_approved(credit_client, demo_user):
    _evaluate(credit_client, GOOD)
    (saved,) = repository.list_credit_applications(demo_user.id)
    assert saved["risk_label"] == "Approved"
    assert saved["risk_percent"] < 33


def test_clearly_bad_profile_is_high_risk(credit_client, demo_user):
    _evaluate(credit_client, BAD)
    (saved,) = repository.list_credit_applications(demo_user.id)
    assert saved["risk_label"] == "High Risk"
    assert saved["risk_percent"] >= 66


def test_the_evaluation_uses_the_champion(app, credit_client, demo_user):
    _evaluate(credit_client, GOOD)
    (saved,) = repository.list_credit_applications(demo_user.id)
    manifest = load_json(os.path.join(ARTIFACTS_DIR, MANIFEST_FILENAME))
    assert saved["model_version"] == model_version_tag(manifest["champion"], manifest["version"])
    assert app.extensions["model_registry"].loaded_model == manifest["champion"]


# model_version: "<code>@<version>", fits the column, screens show the full name

def test_model_version_fits_the_column_for_every_model():
    limit = CreditApplication.model_version.type.length  # read from the model, not written by hand
    versions = [load_json(os.path.join(ARTIFACTS_DIR, MANIFEST_FILENAME))["version"], "2026-11-13.99"]
    for name in MODEL_NAMES:
        for version in versions:
            assert len(model_version_tag(name, version)) <= limit, (name, version)


def test_every_model_has_a_unique_short_code():
    assert set(MODEL_CODES) == set(MODEL_NAMES)
    assert len(set(MODEL_CODES.values())) == len(MODEL_NAMES)
    assert model_version_tag("logistic_regression", "2026-11-13.1") == "lr@2026-11-13.1"


def test_model_version_can_be_parsed_back():
    assert parse_model_version_tag("xgb@2026-11-13.1") == ("xgboost", "2026-11-13.1")
    assert parse_model_version_tag("rf@x") == ("random_forest", "x")
    assert parse_model_version_tag(None) == (None, None)
    assert parse_model_version_tag("unknown@1") == (None, None)
    assert parse_model_version_tag("lr") == (None, None)


def test_result_and_history_show_the_full_model_name_never_the_code(credit_client, demo_user):
    location = _evaluate(credit_client, GOOD)
    manifest = load_json(os.path.join(ARTIFACTS_DIR, MANIFEST_FILENAME))
    code = MODEL_CODES[manifest["champion"]]
    for path in (location, "/credit/history"):
        html = credit_client.get(path).get_data(as_text=True)
        assert DISPLAY_NAMES[manifest["champion"]] in html
        assert f"{code}@" not in html


def test_without_trained_models_the_placeholder_is_used_and_no_model_version_is_stored(
    app, credit_client, demo_user, tmp_path
):
    app.extensions["model_registry"] = ModelRegistry(
        str(tmp_path), EXAMPLE_ARTIFACTS_DIR, app.extensions["credit_predictor"]
    )
    location = _evaluate(credit_client, GOOD)
    (saved,) = repository.list_credit_applications(demo_user.id)
    assert saved["model_version"] is None
    assert "Placeholder model" in credit_client.get(location).get_data(as_text=True)


# Distribution of labels of the champion on the train split (thresholds 0.33 / 0.66)

@pytest.mark.skipif(not os.path.exists(DATASET), reason="the dataset is not in ml/data/raw (it is not versioned)")
def test_champion_label_distribution_on_train_is_not_dominated_by_high_risk(app):
    import joblib
    import numpy as np

    from ml import dataset

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        X_train, _X_test, _y_train, _y_test = dataset.split(dataset.clean(dataset.load()))
    champion = load_json(os.path.join(ARTIFACTS_DIR, MANIFEST_FILENAME))["champion"]
    model = joblib.load(os.path.join(ARTIFACTS_DIR, champion, "model.joblib"))
    risk = model.predict_proba(X_train)[:, 1]

    approved_max = app.config["CREDIT_APPROVED_MAX_RISK"]
    medium_max = app.config["CREDIT_MEDIUM_MAX_RISK"]
    shares = {
        "Approved": float((risk < approved_max).mean()),
        "Medium Risk": float(((risk >= approved_max) & (risk < medium_max)).mean()),
        "High Risk": float((risk >= medium_max).mean()),
    }
    assert np.isclose(sum(shares.values()), 1.0)
    assert shares["High Risk"] < 0.5, shares  # if almost everyone is High Risk, propose thresholds chosen with CV
    assert all(share > 0.01 for share in shares.values()), shares
