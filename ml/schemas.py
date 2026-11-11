"""Format of the training artifacts (manifest.json and metrics.json) and simple validators.

This module only uses the standard library, so the web app can import it.
Each validator returns a list of human-readable errors; an empty list means
the document is valid. See docs/ML_PHASE.md for an annotated example.
"""
import json
import math
import os
import re

from ml.features import FEATURE_SETS, MANIFEST_FILENAME, METRICS_FILENAME, MODEL_FILENAME

# Candidate models, in display order. The name is the URL slug and the folder name.
MODEL_NAMES = ("logistic_regression", "random_forest", "xgboost")
DISPLAY_NAMES = {
    "logistic_regression": "Logistic Regression",
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
}

CV_METRICS = ("roc_auc", "recall", "precision", "f1")
TEST_METRICS = ("roc_auc", "recall", "precision", "f1", "accuracy")

MANIFEST_KEYS = ("version", "trained_at", "dataset", "feature_set", "selection_rule", "champion", "models")
DATASET_KEYS = ("name", "sha256", "rows")
METRICS_KEYS = (
    "model",
    "display_name",
    "model_version",
    "cv",
    "test",
    "confusion_matrix",
    "roc_curve",
    "feature_importance",
    "params",
)
# The part of metrics.json that ml.evaluate.evaluate returns.
EVALUATION_KEYS = ("test", "confusion_matrix", "roc_curve")

MAX_ARTIFACTS_BYTES = 20 * 1024 * 1024
# Tolerance when checking test metrics against the confusion matrix.
METRIC_TOLERANCE = 1e-3

_SHA256 = re.compile(r"[0-9a-f]{64}")
_ISO_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z")


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _is_probability(value):
    return _is_number(value) and 0 <= value <= 1


def _check_keys(doc, expected, where):
    if not isinstance(doc, dict):
        return [f"{where} must be an object"]
    errors = [f"{where} is missing '{key}'" for key in expected if key not in doc]
    errors += [f"{where} has unexpected key '{key}'" for key in doc if key not in expected]
    return errors


def validate_manifest(manifest):
    """Validate the content of manifest.json.

    Format::

        {
          "version": "2026-11-10.1",            # artifact set version, non-empty string
          "trained_at": "2026-11-10T21:30:00Z", # ISO 8601, UTC
          "dataset": {"name": str, "sha256": 64 lowercase hex chars, "rows": int > 0},
          "feature_set": "v2-loan-default",     # a key of ml.features.FEATURE_SETS
          "selection_rule": str,                 # human-readable champion rule
          "champion": "xgboost",                 # one of "models"
          "models": ["logistic_regression", "random_forest", "xgboost"]
        }
    """
    errors = _check_keys(manifest, MANIFEST_KEYS, "manifest")
    if not isinstance(manifest, dict):
        return errors

    if not isinstance(manifest.get("version"), str) or not manifest.get("version"):
        errors.append("manifest.version must be a non-empty string")
    if not isinstance(manifest.get("trained_at"), str) or not _ISO_UTC.fullmatch(manifest["trained_at"]):
        errors.append("manifest.trained_at must be an ISO 8601 UTC timestamp such as 2026-11-10T21:30:00Z")

    dataset = manifest.get("dataset")
    dataset_errors = _check_keys(dataset, DATASET_KEYS, "manifest.dataset")
    errors += dataset_errors
    if isinstance(dataset, dict):
        if not isinstance(dataset.get("name"), str) or not dataset.get("name"):
            errors.append("manifest.dataset.name must be a non-empty string")
        if not isinstance(dataset.get("sha256"), str) or not _SHA256.fullmatch(dataset["sha256"]):
            errors.append("manifest.dataset.sha256 must be 64 lowercase hexadecimal characters")
        rows = dataset.get("rows")
        if not isinstance(rows, int) or isinstance(rows, bool) or rows <= 0:
            errors.append("manifest.dataset.rows must be a positive integer")

    if manifest.get("feature_set") not in FEATURE_SETS:
        errors.append(f"manifest.feature_set must be one of {sorted(FEATURE_SETS)}")
    if not isinstance(manifest.get("selection_rule"), str) or not manifest.get("selection_rule"):
        errors.append("manifest.selection_rule must be a non-empty string")

    models = manifest.get("models")
    if not isinstance(models, list) or not models:
        errors.append("manifest.models must be a non-empty list")
        models = []
    else:
        unknown = [name for name in models if name not in MODEL_NAMES]
        if unknown:
            errors.append(f"manifest.models has unknown models {unknown}; expected names from {list(MODEL_NAMES)}")
        if len(set(models)) != len(models):
            errors.append("manifest.models has duplicates")
    if manifest.get("champion") not in models:
        errors.append("manifest.champion must be one of manifest.models")
    return errors


def validate_metrics(metrics, feature_set=None):
    """Validate the content of one <model>/metrics.json.

    Format::

        {
          "model": "xgboost",                 # one of MODEL_NAMES
          "display_name": "XGBoost",          # DISPLAY_NAMES[model]
          "model_version": "2026-11-10.1",    # same as manifest.version
          "cv":   {"roc_auc": [mean, std], "recall": [...], "precision": [...], "f1": [...]},
          "test": {"roc_auc": x, "recall": x, "precision": x, "f1": x, "accuracy": x},
          "confusion_matrix": [[tn, fp], [fn, tp]],
          "roc_curve": {"fpr": [...], "tpr": [...]},   # same length, 0 -> 1, non-decreasing
          "feature_importance": [{"feature": "CreditScore", "importance": 0.21}, ...],
          "params": {...}                     # classifier hyperparameters
        }

    Every metric is in [0, 1]. Test recall, precision, f1 and accuracy must
    match the confusion matrix. If ``feature_set`` is given, every
    feature_importance entry must name one of its columns.
    """
    errors = _check_keys(metrics, METRICS_KEYS, "metrics")
    if not isinstance(metrics, dict):
        return errors
    where = f"metrics[{metrics.get('model')!r}]"

    model = metrics.get("model")
    if model not in MODEL_NAMES:
        errors.append(f"{where}.model must be one of {list(MODEL_NAMES)}")
    elif metrics.get("display_name") != DISPLAY_NAMES[model]:
        errors.append(f"{where}.display_name must be {DISPLAY_NAMES[model]!r}")
    if not isinstance(metrics.get("model_version"), str) or not metrics.get("model_version"):
        errors.append(f"{where}.model_version must be a non-empty string")

    cv = metrics.get("cv")
    errors += _check_keys(cv, CV_METRICS, f"{where}.cv")
    if isinstance(cv, dict):
        for name in CV_METRICS:
            pair = cv.get(name)
            if not (isinstance(pair, list) and len(pair) == 2 and _is_probability(pair[0])
                    and _is_number(pair[1]) and 0 <= pair[1] <= 1):
                errors.append(f"{where}.cv.{name} must be [mean, std] with values in [0, 1]")

    test = metrics.get("test")
    errors += _check_keys(test, TEST_METRICS, f"{where}.test")
    if isinstance(test, dict):
        for name in TEST_METRICS:
            if not _is_probability(test.get(name)):
                errors.append(f"{where}.test.{name} must be a number in [0, 1]")

    matrix = metrics.get("confusion_matrix")
    matrix_ok = (
        isinstance(matrix, list) and len(matrix) == 2
        and all(isinstance(row, list) and len(row) == 2 for row in matrix)
        and all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for row in matrix for v in row)
        and sum(sum(row) for row in matrix) > 0
    )
    if not matrix_ok:
        errors.append(f"{where}.confusion_matrix must be [[tn, fp], [fn, tp]] with non-negative integers")
    elif isinstance(test, dict) and all(_is_probability(test.get(name)) for name in TEST_METRICS):
        errors += _check_matrix_agrees(matrix, test, where)

    errors += _check_roc_curve(metrics.get("roc_curve"), where)

    importance = metrics.get("feature_importance")
    if not isinstance(importance, list) or not importance:
        errors.append(f"{where}.feature_importance must be a non-empty list")
    else:
        columns = FEATURE_SETS[feature_set]["columns"] if feature_set in FEATURE_SETS else None
        for item in importance:
            if not (isinstance(item, dict) and set(item) == {"feature", "importance"}
                    and isinstance(item["feature"], str) and _is_number(item["importance"])):
                errors.append(f"{where}.feature_importance items must be {{'feature': str, 'importance': number}}")
                break
            if columns is not None and item["feature"] not in columns:
                errors.append(f"{where}.feature_importance names unknown feature {item['feature']!r}")

    if not isinstance(metrics.get("params"), dict):
        errors.append(f"{where}.params must be an object")
    return errors


def _check_matrix_agrees(matrix, test, where):
    (tn, fp), (fn, tp) = matrix
    total = tn + fp + fn + tp
    recall = tp / (tp + fn) if tp + fn else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    expected = {"recall": recall, "precision": precision, "f1": f1, "accuracy": (tn + tp) / total}
    return [
        f"{where}.test.{name} is {test[name]} but the confusion matrix gives {value:.4f}"
        for name, value in expected.items()
        if abs(test[name] - value) > METRIC_TOLERANCE
    ]


def _check_roc_curve(curve, where):
    errors = _check_keys(curve, ("fpr", "tpr"), f"{where}.roc_curve")
    if not isinstance(curve, dict) or errors:
        return errors
    fpr, tpr = curve["fpr"], curve["tpr"]
    if not (isinstance(fpr, list) and isinstance(tpr, list) and len(fpr) == len(tpr) >= 2):
        return [f"{where}.roc_curve.fpr and tpr must be lists of the same length (at least 2)"]
    if not all(_is_probability(v) for v in fpr + tpr):
        return [f"{where}.roc_curve values must be numbers in [0, 1]"]
    for name, values in (("fpr", fpr), ("tpr", tpr)):
        if any(b < a for a, b in zip(values, values[1:])):
            errors.append(f"{where}.roc_curve.{name} must be non-decreasing")
        if values[0] != 0 or values[-1] != 1:
            errors.append(f"{where}.roc_curve.{name} must start at 0 and end at 1")
    return errors


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def artifacts_size(directory):
    """Total size in bytes of every file under ``directory``."""
    return sum(
        os.path.getsize(os.path.join(root, name))
        for root, _dirs, files in os.walk(directory)
        for name in files
    )


def validate_artifacts(directory, require_models=False):
    """Validate a whole artifact folder: manifest.json plus each <model>/metrics.json.

    Also checks that every metrics file belongs to its folder, shares the
    manifest version and only names features of the manifest feature set.
    With ``require_models`` (real artifacts), each <model>/model.joblib must
    exist and the folder must stay under ``MAX_ARTIFACTS_BYTES``.
    """
    manifest_path = os.path.join(directory, MANIFEST_FILENAME)
    if not os.path.exists(manifest_path):
        return [f"{manifest_path} does not exist"]
    manifest = load_json(manifest_path)
    errors = validate_manifest(manifest)
    if errors:
        return errors

    for name in manifest["models"]:
        metrics_path = os.path.join(directory, name, METRICS_FILENAME)
        if not os.path.exists(metrics_path):
            errors.append(f"{metrics_path} does not exist")
            continue
        metrics = load_json(metrics_path)
        errors += validate_metrics(metrics, manifest["feature_set"])
        if metrics.get("model") != name:
            errors.append(f"{metrics_path} describes {metrics.get('model')!r}, not {name!r}")
        if metrics.get("model_version") != manifest["version"]:
            errors.append(f"{metrics_path} model_version differs from manifest.version")
        if require_models and not os.path.exists(os.path.join(directory, name, MODEL_FILENAME)):
            errors.append(f"{name}/{MODEL_FILENAME} does not exist")

    if require_models and artifacts_size(directory) >= MAX_ARTIFACTS_BYTES:
        errors.append(f"{directory} is {artifacts_size(directory)} bytes; the limit is {MAX_ARTIFACTS_BYTES}")
    return errors
