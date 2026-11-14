"""Tests for ml/train.py: command line and champion selection (owner: ml)."""
import os

import pytest

from ml import train
from ml.features import ARTIFACTS_DIR, EXAMPLE_ARTIFACTS_DIR, MANIFEST_FILENAME
from ml.schemas import MODEL_NAMES, load_json, validate_artifacts

SAMPLE = os.path.join(os.path.dirname(__file__), "fixtures", "loan_default_sample.csv")


def _cv(roc_auc, recall):
    """Minimal metrics.json content for select_champion (test metrics deliberately absurd)."""
    return {
        "cv": {"roc_auc": [roc_auc, 0.01], "recall": [recall, 0.01], "precision": [0.2, 0.01], "f1": [0.3, 0.01]},
        "test": {"roc_auc": 1.0, "recall": 1.0, "precision": 1.0, "f1": 1.0, "accuracy": 1.0},
    }


# Command line (passes now)

def test_cli_defaults_point_to_the_raw_dataset_and_the_artifacts_folder():
    args = train.parse_args([])
    assert args.data.endswith(os.path.join("raw", "Loan_default.csv"))
    assert args.out == ARTIFACTS_DIR


def test_cli_accepts_custom_paths():
    args = train.parse_args(["--data", "sample.csv", "--out", "out"])
    assert (args.data, args.out) == ("sample.csv", "out")


def test_champion_rule_constants():
    assert train.CV_FOLDS == 5
    assert train.CHAMPION_AUC_MARGIN == 0.01


# Behaviour

def test_highest_cv_auc_wins_when_the_gap_is_large():
    """xgboost 0.75 vs 0.70 and 0.72: xgboost wins even with lower recall."""
    metrics = {
        "logistic_regression": _cv(0.70, 0.80),
        "random_forest": _cv(0.72, 0.70),
        "xgboost": _cv(0.75, 0.50),
    }
    assert train.select_champion(metrics) == "xgboost"


def test_recall_breaks_a_tie_closer_than_0_01():
    """xgboost 0.718 vs logistic_regression 0.712 (gap 0.006): the higher CV recall wins."""
    metrics = {
        "logistic_regression": _cv(0.712, 0.66),
        "random_forest": _cv(0.700, 0.90),
        "xgboost": _cv(0.718, 0.62),
    }
    assert train.select_champion(metrics) == "logistic_regression"


def test_selection_never_uses_test_metrics():
    """Swapping the test blocks does not change the champion."""
    metrics = {"random_forest": _cv(0.70, 0.5), "xgboost": _cv(0.75, 0.5)}
    metrics["random_forest"]["test"]["roc_auc"] = 0.99
    metrics["xgboost"]["test"]["roc_auc"] = 0.10
    assert train.select_champion(metrics) == "xgboost"


def test_exact_tie_goes_to_the_first_model_in_order():
    """Same CV AUC and recall: the first name in MODEL_NAMES wins."""
    metrics = {name: _cv(0.7, 0.6) for name in MODEL_NAMES}
    assert train.select_champion(metrics) == MODEL_NAMES[0]


def test_empty_input_is_rejected():
    """No models raises ValueError."""
    with pytest.raises(ValueError):
        train.select_champion({})


def test_example_manifest_champion_follows_the_rule():
    """select_champion on the example metrics returns the example manifest champion."""
    manifest = load_json(os.path.join(EXAMPLE_ARTIFACTS_DIR, MANIFEST_FILENAME))
    metrics = {name: load_json(os.path.join(EXAMPLE_ARTIFACTS_DIR, name, "metrics.json")) for name in MODEL_NAMES}
    assert train.select_champion(metrics) == manifest["champion"]


def test_run_on_the_sample_writes_valid_artifacts(tmp_path):
    """run(SAMPLE, tmp_path) writes manifest, metrics and models that pass validate_artifacts."""
    manifest = train.run(SAMPLE, str(tmp_path))
    assert validate_artifacts(str(tmp_path), require_models=True) == []
    assert manifest["dataset"]["rows"] == 60
