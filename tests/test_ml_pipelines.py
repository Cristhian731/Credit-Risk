"""Tests for ml/pipelines.py."""
import os

import pytest

from ml.pipelines import build_pipeline
from ml.schemas import MODEL_NAMES

SAMPLE = os.path.join(os.path.dirname(__file__), "fixtures", "loan_default_sample.csv")


def _sample_split():
    from ml import dataset

    return dataset.split(dataset.load(SAMPLE))


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_pipeline_fits_the_sample_and_returns_probabilities(name):
    """Each pipeline fits the 48 training rows and predict_proba gives one probability pair per row."""
    X_train, X_test, y_train, _y_test = _sample_split()
    model = build_pipeline(name, scale_pos_weight=5.0).fit(X_train, y_train)
    proba = model.predict_proba(X_test)
    assert proba.shape == (len(X_test), 2)
    assert ((proba >= 0) & (proba <= 1)).all()


def test_pipeline_ignores_unknown_employment_categories():
    """An EmploymentType never seen in training does not raise."""
    X_train, X_test, y_train, _y_test = _sample_split()
    model = build_pipeline("logistic_regression").fit(X_train, y_train)
    X_test = X_test.copy()
    X_test["EmploymentType"] = "Retired"
    model.predict_proba(X_test)


@pytest.mark.parametrize("name", ["logistic_regression", "random_forest"])
def test_sklearn_models_use_balanced_class_weight(name):
    """Logistic regression and random forest use class_weight='balanced'."""
    assert build_pipeline(name)[-1].get_params()["class_weight"] == "balanced"


def test_xgboost_uses_the_given_scale_pos_weight():
    """build_pipeline('xgboost', scale_pos_weight=7.6) passes it to XGBClassifier."""
    assert build_pipeline("xgboost", scale_pos_weight=7.6)[-1].get_params()["scale_pos_weight"] == 7.6


def test_unknown_model_name_is_rejected():
    """An unknown name raises ValueError."""
    with pytest.raises(ValueError):
        build_pipeline("svm")
