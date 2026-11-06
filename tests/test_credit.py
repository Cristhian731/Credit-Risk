"""Tests for the credit evaluation module (form, predictor and routes)."""
import pytest

from app.credit.forms import validate_form
from app.credit.services import PredictionService
from ml.features import FEATURE_ORDER

VALID_FORM = {
    "age": "35",
    "monthly_income": "4000",
    "employment_status": "employed",
    "years_employment": "8",
    "credit_score": "760",
    "existing_debt": "2000",
    "dti_ratio": "15",
    "loan_amount": "10000",
    "loan_term": "36",
    "previous_loans": "2",
    "payment_history": "good",
}


class _FixedRiskModel:
    """Fake classifier that always returns the given default probability."""

    def __init__(self, risk):
        self.risk = risk

    def predict_proba(self, x):
        return [[1 - self.risk, self.risk]]


class _IdentityScaler:
    def transform(self, x):
        return x


def _service_with_risk(risk):
    service = PredictionService("missing.pkl", "missing.pkl", approved_max=0.33, medium_max=0.66)
    service.model = _FixedRiskModel(risk)
    service.scaler = _IdentityScaler()
    return service


@pytest.fixture
def credit_client(app):
    app.config["FAKE_AUTH"] = True
    return app.test_client()


# Form validation

def test_valid_form_returns_every_feature_encoded():
    values, errors = validate_form(VALID_FORM)
    assert errors == []
    assert set(values) == set(FEATURE_ORDER)
    assert values["employment_status"] == 0
    assert values["payment_history"] == 0
    assert isinstance(values["age"], int)


def test_gender_is_not_a_feature():
    assert "gender" not in FEATURE_ORDER


@pytest.mark.parametrize(
    "field, value",
    [("age", "abc"), ("age", "17"), ("credit_score", "900"), ("dti_ratio", "-1"), ("loan_amount", "")],
)
def test_invalid_numeric_value_is_rejected(field, value):
    values, errors = validate_form({**VALID_FORM, field: value})
    assert field not in values
    assert len(errors) == 1


@pytest.mark.parametrize("field", ["employment_status", "payment_history"])
def test_invalid_choice_is_rejected(field):
    values, errors = validate_form({**VALID_FORM, field: "unknown"})
    assert field not in values
    assert len(errors) == 1


# Prediction service

@pytest.mark.parametrize(
    "risk, label",
    [(0.10, "Approved"), (0.329, "Approved"), (0.33, "Medium Risk"), (0.50, "Medium Risk"),
     (0.66, "High Risk"), (0.95, "High Risk")],
)
def test_risk_is_mapped_to_label(risk, label):
    values, _ = validate_form(VALID_FORM)
    result = _service_with_risk(risk).predict(values)
    assert result["label"] == label
    assert result["risk_percent"] == round(risk * 100, 1)
    assert result["recommendation"]


def test_missing_artifacts_do_not_crash_but_prediction_fails():
    service = PredictionService("missing.pkl", "missing.pkl", approved_max=0.33, medium_max=0.66)
    assert service.is_ready is False
    with pytest.raises(RuntimeError):
        service.predict({})


def test_saved_placeholder_model_matches_feature_schema(app):
    service = app.extensions["credit_predictor"]
    assert service.is_ready
    assert service.model.n_features_in_ == len(FEATURE_ORDER)


# Routes

def test_form_page_shows_every_field(credit_client):
    html = credit_client.get("/credit/").get_data(as_text=True)
    for name in FEATURE_ORDER:
        assert f'name="{name}"' in html


def test_valid_submission_redirects_to_result(credit_client):
    response = credit_client.post("/credit/", data=VALID_FORM)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/credit/result")

    result = credit_client.get("/credit/result")
    assert result.status_code == 200
    assert "Estimated default risk" in result.get_data(as_text=True)


def test_invalid_submission_keeps_form_data(credit_client):
    response = credit_client.post("/credit/", data={**VALID_FORM, "credit_score": "900"})
    html = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "must be between" in html
    assert 'value="35"' in html


def test_result_without_submission_redirects_to_form(credit_client):
    response = credit_client.get("/credit/result")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/credit/")


def test_unavailable_model_returns_503(app, credit_client):
    app.extensions["credit_predictor"] = PredictionService(
        "missing.pkl", "missing.pkl", approved_max=0.33, medium_max=0.66
    )
    response = credit_client.post("/credit/", data=VALID_FORM)
    assert response.status_code == 503
    assert "not available" in response.get_data(as_text=True)
