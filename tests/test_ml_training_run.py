"""Tests for the real training run: champion ties, dataset hash, reports and artifacts."""
import json
import os
import warnings

import numpy as np
import pytest

from app.credit.forms import validate_form
from ml import dataset, train
from ml.evaluate import evaluate_subgroups
from ml.features import MANIFEST_FILENAME, to_model_frame
from ml.schemas import (
    DATA_REPORT_FILENAME,
    EXPERIMENTS_FILENAME,
    MODEL_NAMES,
    OVERFITTING_FILENAME,
    SUBGROUPS_FILENAME,
    load_json,
    validate_artifacts,
    validate_data_report,
    validate_experiments,
    validate_manifest,
    validate_overfitting,
    validate_subgroups,
)

SAMPLE = os.path.join(os.path.dirname(__file__), "fixtures", "loan_default_sample.csv")

FORM = {
    "age": "35", "monthly_income": "4000", "employment_status": "employed",
    "years_employment": "2.5", "credit_score": "700", "existing_debt": "2000",
    "dti_ratio": "15", "loan_amount": "10000", "loan_term": "36",
    "previous_loans": "2", "payment_history": "good",
}


def _cv(roc_auc, recall):
    return {"cv": {"roc_auc": [roc_auc, 0.01], "recall": [recall, 0.01]}}


# Champion rule

def test_tie_goes_to_the_highest_cv_recall_even_with_lower_auc():
    """Gap 0.009 (< 0.01): the model with the best AUC loses to the one with more recall."""
    metrics = {
        "logistic_regression": _cv(0.710, 0.61),
        "random_forest": _cv(0.719, 0.58),
        "xgboost": _cv(0.700, 0.75),
    }
    # xgboost is 0.019 below the best, so it is out; logistic_regression ties with random_forest.
    assert train.select_champion(metrics) == "logistic_regression"


def test_a_gap_of_exactly_the_margin_is_not_a_tie():
    metrics = {"logistic_regression": _cv(0.70, 0.90), "xgboost": _cv(0.71, 0.50)}
    assert train.select_champion(metrics) == "xgboost"


def test_recall_decides_among_three_tied_models():
    metrics = {
        "logistic_regression": _cv(0.7150, 0.60),
        "random_forest": _cv(0.7120, 0.66),
        "xgboost": _cv(0.7200, 0.62),
    }
    assert train.select_champion(metrics) == "random_forest"


# Dataset

def test_load_registers_the_sha256_and_warns_when_it_differs():
    with pytest.warns(UserWarning, match="SHA-256"):
        df = dataset.load(SAMPLE)
    assert df.attrs["sha256"] == dataset.file_sha256(SAMPLE)
    assert df.attrs["sha256"] != dataset.EXPECTED_SHA256


def test_data_report_has_statistics_and_no_raw_rows():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = dataset.load(SAMPLE)
    cleaned = dataset.clean(raw)
    _X_train, _X_test, y_train, y_test = dataset.split(cleaned)
    report = dataset.build_data_report(raw, cleaned, y_train, y_test)

    assert validate_data_report(report) == []
    assert report["before"]["rows"] == 60 and report["after"]["null_cells"] == 0
    assert report["split"]["train_rows"] + report["split"]["test_rows"] == 60
    text = json.dumps(report)
    assert not any(loan_id in text for loan_id in raw[dataset.ID_COLUMN])


def test_clean_removes_duplicates():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = dataset.load(SAMPLE)
    import pandas as pd

    doubled = pd.concat([raw, raw.iloc[:3]], ignore_index=True)
    assert len(dataset.clean(doubled)) == 60


# Features

def test_to_model_frame_converts_monthly_income_to_annual():
    values, errors = validate_form(FORM)
    assert errors == []
    assert to_model_frame(values).iloc[0]["Income"] == 48000


# Evaluation by subgroup

class _Proba:
    def __init__(self, p):
        self.p = np.asarray(p, dtype=float)

    def predict_proba(self, X):
        return np.column_stack([1 - self.p, self.p])


def test_subgroups_report_age_ranges_and_employment_types():
    import pandas as pd

    rng = np.random.default_rng(0)
    n = 400
    X = pd.DataFrame({
        "Age": rng.integers(18, 70, n),
        "EmploymentType": rng.choice(["Full-time", "Part-time"], n),
    })
    y = rng.integers(0, 2, n)
    result = evaluate_subgroups(_Proba(np.clip(y * 0.4 + rng.random(n) * 0.6, 0, 1)), X, y)
    assert set(result) == {"age_range", "employment_type"}
    assert set(result["employment_type"]) == {"Full-time", "Part-time"}
    assert sum(group["rows"] for group in result["age_range"].values()) == n
    assert all("roc_auc" in group for group in result["employment_type"].values())


# Full run on the synthetic sample

@pytest.fixture(scope="module")
def sample_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("artifacts")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        manifest = train.run(SAMPLE, str(out), n_iter=2, n_jobs=1)
    return str(out), manifest


def test_run_writes_every_artifact_and_they_validate(sample_run):
    out, manifest = sample_run
    assert validate_artifacts(out, require_models=True) == []
    assert manifest["dataset"]["rows"] == 60
    assert manifest["champion"] in MODEL_NAMES
    for filename in (DATA_REPORT_FILENAME, EXPERIMENTS_FILENAME, OVERFITTING_FILENAME, SUBGROUPS_FILENAME):
        assert os.path.exists(os.path.join(out, filename))


def test_manifest_records_the_hash_and_the_success_criteria(sample_run):
    out, _manifest = sample_run
    manifest = load_json(os.path.join(out, MANIFEST_FILENAME))
    assert validate_manifest(manifest) == []
    assert manifest["dataset"]["sha256"] == dataset.file_sha256(SAMPLE)
    assert manifest["dataset"]["sha256_matches_expected"] is False
    criteria = manifest["success_criteria"]
    assert [item["threshold"] for item in criteria["results"]] == [0.70, 0.60, 0.02]
    assert criteria["all_passed"] == all(item["passed"] for item in criteria["results"])


def test_experiments_state_that_the_test_split_is_used_once(sample_run):
    out, _manifest = sample_run
    experiments = load_json(os.path.join(out, EXPERIMENTS_FILENAME))
    assert validate_experiments(experiments) == []
    assert "Train split only" in experiments["protocol"]["selection_data"]
    assert "exactly once" in experiments["protocol"]["test_usage"]
    assert set(experiments["models"]) == set(MODEL_NAMES)
    assert all(len(entry["runs"]) == 2 for entry in experiments["models"].values())


def test_overfitting_and_subgroup_files_validate(sample_run):
    out, _manifest = sample_run
    assert validate_overfitting(load_json(os.path.join(out, OVERFITTING_FILENAME))) == []
    assert validate_subgroups(load_json(os.path.join(out, SUBGROUPS_FILENAME))) == []


def test_new_validators_reject_malformed_documents():
    assert validate_data_report({}) != []
    assert validate_experiments({"models": {}}) != []
    assert validate_overfitting([]) != []
    assert validate_subgroups({"version": "x"}) != []


def test_subgroups_include_findings_about_age(sample_run):
    out, manifest = sample_run
    document = load_json(os.path.join(out, SUBGROUPS_FILENAME))
    assert validate_subgroups(document) == []
    ids = [item["id"] for item in document["findings"]]
    assert ids == ["age_bias", "employment_type_gap"]
    assert all(item["model"] == manifest["champion"] for item in document["findings"])
