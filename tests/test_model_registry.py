"""Tests for ModelRegistry in app/credit/services.py."""
import json
import shutil

import joblib
import pytest

from app.credit.forms import validate_form
from app.credit.services import ModelRegistry
from ml.features import EXAMPLE_ARTIFACTS_DIR, MANIFEST_FILENAME
from ml.schemas import CHAMPION_AUC_MARGIN, MODEL_CODES, MODEL_NAMES, model_version_tag


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


def test_choosing_a_model_without_trained_models_raises_runtime_error(registry, values):
    with pytest.raises(RuntimeError):
        registry.predict(values, model="xgboost")


# Behaviour with trained models

@pytest.fixture(scope="module")
def sample_artifacts(tmp_path_factory):
    """Models really trained on the synthetic sample (small search, one process), shared by the tests."""
    import os
    import warnings

    from ml import train

    sample = os.path.join(os.path.dirname(__file__), "fixtures", "loan_default_sample.csv")
    folder = tmp_path_factory.mktemp("sample_artifacts")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        train.run(sample, str(folder), n_iter=2, n_jobs=1)
    return folder


@pytest.fixture
def sample_registry(app, sample_artifacts, tmp_path):
    shutil.copytree(sample_artifacts, tmp_path, dirs_exist_ok=True)
    return ModelRegistry(str(tmp_path), EXAMPLE_ARTIFACTS_DIR, app.extensions["credit_predictor"])


def test_with_trained_models_predict_uses_the_champion(sample_registry, values):
    """predict(values) loads the manifest champion and returns label, risk_percent 0-100 and recommendation."""
    result = sample_registry.predict(values)
    assert set(result) == {"label", "risk_percent", "recommendation", "model", "model_version"}
    assert 0 <= result["risk_percent"] <= 100
    champion = sample_registry.catalog()["manifest"]["champion"]
    assert sample_registry.loaded_model == champion == result["model"]
    assert result["model_version"] == model_version_tag(champion, sample_registry.catalog()["manifest"]["version"])


def test_the_champion_is_loaded_once_and_only_on_first_prediction(sample_registry, values, monkeypatch):
    """joblib.load is called once across two predictions, and not before the first one."""
    calls = []
    real_load = joblib.load
    monkeypatch.setattr(joblib, "load", lambda path: calls.append(path) or real_load(path))
    assert calls == []
    sample_registry.predict(values)
    sample_registry.predict(values)
    assert len(calls) == 1


def test_a_missing_model_file_raises_runtime_error(trained_registry, values):
    """With a manifest but no model.joblib, predict raises RuntimeError (the route answers 503)."""
    with pytest.raises(RuntimeError):
        trained_registry.predict(values)


def test_at_most_one_model_is_kept_in_memory(sample_registry, values):
    """Predicting with random_forest after xgboost releases xgboost: only one model stays loaded."""
    sample_registry.predict(values, model="xgboost")
    sample_registry.predict(values, model="random_forest")
    assert sample_registry.loaded_model == "random_forest"


def test_unknown_model_name_is_rejected(trained_registry, values):
    """predict(values, model='svm') raises ValueError."""
    with pytest.raises(ValueError):
        trained_registry.predict(values, model="svm")


def test_a_chosen_model_is_used_even_when_it_is_not_the_champion(sample_registry, values):
    other = next(name for name in MODEL_NAMES if name != sample_registry.catalog()["manifest"]["champion"])
    result = sample_registry.predict(values, model=other)
    assert result["model"] == other
    assert result["model_version"].startswith(MODEL_CODES[other] + "@")


def test_the_catalog_includes_experiments_and_overfitting(sample_registry):
    catalog = sample_registry.catalog()
    assert set(catalog["experiments"]["models"]) == set(MODEL_NAMES)
    assert set(catalog["overfitting"]["models"]) == set(MODEL_NAMES)


def test_the_example_catalog_has_no_experiments_or_overfitting(registry):
    catalog = registry.catalog()
    assert catalog["experiments"] is None and catalog["overfitting"] is None


def test_selection_summary_marks_the_champion_and_the_tie(sample_registry):
    summary = sample_registry.selection_summary()
    assert [row["name"] for row in summary] == list(MODEL_NAMES)
    assert sum(row["is_champion"] for row in summary) == 1
    best = max(row["cv_roc_auc"] for row in summary)
    assert all(row["tied"] == (best - row["cv_roc_auc"] < CHAMPION_AUC_MARGIN) for row in summary)
