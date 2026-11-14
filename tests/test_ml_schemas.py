"""Contract tests for the artifact format (ml/schemas.py) and the example artifacts."""
import copy
import os

import pytest

from ml.features import ARTIFACTS_DIR, EXAMPLE_ARTIFACTS_DIR, MANIFEST_FILENAME
from ml.schemas import (
    DISPLAY_NAMES,
    EVALUATION_KEYS,
    METRICS_KEYS,
    MODEL_NAMES,
    load_json,
    validate_artifacts,
    validate_manifest,
    validate_metrics,
)

REAL_MANIFEST = os.path.join(ARTIFACTS_DIR, MANIFEST_FILENAME)


@pytest.fixture
def manifest():
    return load_json(os.path.join(EXAMPLE_ARTIFACTS_DIR, MANIFEST_FILENAME))


@pytest.fixture
def metrics():
    return load_json(os.path.join(EXAMPLE_ARTIFACTS_DIR, "xgboost", "metrics.json"))


# The example artifacts follow the contract

def test_example_artifacts_are_valid():
    assert validate_artifacts(EXAMPLE_ARTIFACTS_DIR) == []


def test_example_manifest_lists_the_three_models_and_a_champion(manifest):
    assert validate_manifest(manifest) == []
    assert manifest["models"] == list(MODEL_NAMES)
    assert manifest["champion"] in MODEL_NAMES
    assert manifest["feature_set"] == "v2-loan-default"


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_example_metrics_are_valid(name):
    metrics = load_json(os.path.join(EXAMPLE_ARTIFACTS_DIR, name, "metrics.json"))
    assert validate_metrics(metrics, "v2-loan-default") == []
    assert metrics["display_name"] == DISPLAY_NAMES[name]
    assert 40 <= len(metrics["roc_curve"]["fpr"]) <= 60


def test_evaluation_keys_are_part_of_metrics():
    assert set(EVALUATION_KEYS) <= set(METRICS_KEYS)


# The validators reject broken documents

@pytest.mark.parametrize("change, message", [
    (lambda m: m.pop("champion"), "missing 'champion'"),
    (lambda m: m.update(extra=1), "unexpected key 'extra'"),
    (lambda m: m.update(champion="svm"), "champion"),
    (lambda m: m.update(models=["svm"]), "unknown models"),
    (lambda m: m.update(feature_set="v9"), "feature_set"),
    (lambda m: m.update(trained_at="10/11/2026"), "trained_at"),
    (lambda m: m["dataset"].update(sha256="abc"), "sha256"),
    (lambda m: m["dataset"].update(rows=0), "rows"),
])
def test_invalid_manifest_is_rejected(manifest, change, message):
    broken = copy.deepcopy(manifest)
    change(broken)
    errors = validate_manifest(broken)
    assert any(message in error for error in errors), errors


@pytest.mark.parametrize("change, message", [
    (lambda m: m.pop("params"), "missing 'params'"),
    (lambda m: m.update(model="svm"), "model must be one of"),
    (lambda m: m.update(display_name="XGB"), "display_name"),
    (lambda m: m["cv"].update(roc_auc=[0.7]), "cv.roc_auc"),
    (lambda m: m["test"].update(roc_auc=1.2), "test.roc_auc"),
    (lambda m: m["test"].update(recall=0.99), "confusion matrix gives"),
    (lambda m: m.update(confusion_matrix=[[1, 2, 3]]), "confusion_matrix"),
    (lambda m: m["roc_curve"]["tpr"].reverse(), "non-decreasing"),
    (lambda m: m["roc_curve"]["fpr"].pop(), "same length"),
    (lambda m: m["feature_importance"].append({"feature": "Gender", "importance": 0.1}), "unknown feature"),
])
def test_invalid_metrics_are_rejected(metrics, change, message):
    broken = copy.deepcopy(metrics)
    change(broken)
    errors = validate_metrics(broken, "v2-loan-default")
    assert any(message in error for error in errors), errors


def test_artifact_folder_checks_versions_and_folder_names(tmp_path, manifest, metrics):
    import json

    (tmp_path / MANIFEST_FILENAME).write_text(json.dumps({**manifest, "models": ["xgboost"], "champion": "xgboost"}))
    (tmp_path / "xgboost").mkdir()
    (tmp_path / "xgboost" / "metrics.json").write_text(json.dumps({**metrics, "model_version": "other"}))
    errors = validate_artifacts(str(tmp_path), require_models=True)
    assert any("model_version differs" in error for error in errors)
    assert any("model.joblib does not exist" in error for error in errors)


def test_missing_manifest_is_reported(tmp_path):
    assert "does not exist" in validate_artifacts(str(tmp_path))[0]


# Real artifacts (Sprint 1 onwards): valid, complete and under 20 MB

@pytest.mark.skipif(not os.path.exists(REAL_MANIFEST), reason="no trained artifacts in ml/artifacts yet")
def test_real_artifacts_are_valid_complete_and_small():
    assert validate_artifacts(ARTIFACTS_DIR, require_models=True) == []
