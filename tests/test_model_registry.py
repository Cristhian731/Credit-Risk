"""Tests for ModelRegistry in app/credit/services.py."""
import json
import shutil

import joblib
import pytest

from app.credit.forms import validate_form
from app.credit.services import ModelRegistry
from ml.features import EXAMPLE_ARTIFACTS_DIR, MANIFEST_FILENAME
from ml.schemas import MODEL_NAMES

SPRINT_1_ML = pytest.mark.skip(reason="Sprint 1 - owner: ml")
SPRINT_2_ML = pytest.mark.skip(reason="Sprint 2 - owner: ml")

FORM = {
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


@pytest.fixture
def values():
    clean, errors = validate_form(FORM)
    assert errors == []
    return clean


@pytest.fixture
def registry(app, tmp_path):
    """Registry over an empty artifacts folder: no trained models yet."""
    return ModelRegistry(str(tmp_path), EXAMPLE_ARTIFACTS_DIR, app.extensions["credit_predictor"])


@pytest.fixture
def trained_registry(app, tmp_path):
    """Registry over a copy of the example artifacts, as if they were real."""
    shutil.copytree(EXAMPLE_ARTIFACTS_DIR, tmp_path, dirs_exist_ok=True)
    return ModelRegistry(str(tmp_path), EXAMPLE_ARTIFACTS_DIR, app.extensions["credit_predictor"])


# Current behaviour (passes now)

def test_app_creates_a_registry_backed_by_the_placeholder(app):
    registry = app.extensions["model_registry"]
    assert isinstance(registry, ModelRegistry)
    assert registry.fallback is app.extensions["credit_predictor"]


def test_without_a_manifest_predict_matches_the_placeholder(registry, values, app):
    assert registry.has_trained_models is False
    assert registry.predict(values) == app.extensions["credit_predictor"].predict(values)


def test_without_a_manifest_the_catalog_is_the_example(registry):
    catalog = registry.catalog()
    assert catalog["is_example"] is True
    assert list(catalog["metrics"]) == list(MODEL_NAMES)
    assert catalog["manifest"]["champion"] in MODEL_NAMES


def test_with_a_manifest_the_catalog_reads_the_real_folder(trained_registry, tmp_path):
    manifest = json.loads((tmp_path / MANIFEST_FILENAME).read_text())
    (tmp_path / MANIFEST_FILENAME).write_text(json.dumps({**manifest, "version": "real"}))
    catalog = trained_registry.catalog()
    assert catalog["is_example"] is False
    assert catalog["manifest"]["version"] == "real"


def test_creating_the_registry_loads_no_model(app, tmp_path, monkeypatch):
    def fail(*_args, **_kwargs):
        raise AssertionError("a model was loaded at start-up")

    shutil.copytree(EXAMPLE_ARTIFACTS_DIR, tmp_path, dirs_exist_ok=True)
    monkeypatch.setattr(joblib, "load", fail)
    registry = ModelRegistry(str(tmp_path), EXAMPLE_ARTIFACTS_DIR, app.extensions["credit_predictor"])
    registry.catalog()
    assert registry.loaded_model is None


def test_choosing_a_model_is_not_available_yet(registry, values):
    with pytest.raises(NotImplementedError):
        registry.predict(values, model="xgboost")


# Skeleton tests for the ml owner

@pytest.fixture
def sample_registry(app, tmp_path):
    """Registry over models really trained on the synthetic sample (needs ml.train.run)."""
    import os

    from ml import train

    sample = os.path.join(os.path.dirname(__file__), "fixtures", "loan_default_sample.csv")
    train.run(sample, str(tmp_path))
    return ModelRegistry(str(tmp_path), EXAMPLE_ARTIFACTS_DIR, app.extensions["credit_predictor"])


@SPRINT_1_ML
def test_with_trained_models_predict_uses_the_champion(sample_registry, values):
    """predict(values) loads the manifest champion and returns label, risk_percent 0-100 and recommendation."""
    result = sample_registry.predict(values)
    assert set(result) == {"label", "risk_percent", "recommendation"}
    assert 0 <= result["risk_percent"] <= 100
    assert sample_registry.loaded_model == sample_registry.catalog()["manifest"]["champion"]


@SPRINT_1_ML
def test_the_champion_is_loaded_once_and_only_on_first_prediction(sample_registry, values, monkeypatch):
    """joblib.load is called once across two predictions, and not before the first one."""
    calls = []
    real_load = joblib.load
    monkeypatch.setattr(joblib, "load", lambda path: calls.append(path) or real_load(path))
    assert calls == []
    sample_registry.predict(values)
    sample_registry.predict(values)
    assert len(calls) == 1


@SPRINT_1_ML
def test_a_missing_model_file_raises_runtime_error(trained_registry, values):
    """With a manifest but no model.joblib, predict raises RuntimeError (the route answers 503)."""
    with pytest.raises(RuntimeError):
        trained_registry.predict(values)


@SPRINT_2_ML
def test_at_most_one_model_is_kept_in_memory(sample_registry, values):
    """Predicting with random_forest after xgboost releases xgboost: only one model stays loaded."""
    sample_registry.predict(values, model="xgboost")
    sample_registry.predict(values, model="random_forest")
    assert sample_registry.loaded_model == "random_forest"


@SPRINT_2_ML
def test_unknown_model_name_is_rejected(trained_registry, values):
    """predict(values, model='svm') raises ValueError."""
    with pytest.raises(ValueError):
        trained_registry.predict(values, model="svm")
