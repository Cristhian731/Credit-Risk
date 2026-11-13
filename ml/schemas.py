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

# Short codes used to store which model made a prediction: credit_applications.model_version
# is "<code>@<manifest.version>", for example "lr@2026-11-13.1". The column holds 30 characters,
# so the codes stay short. Screens always show DISPLAY_NAMES, never the code.
MODEL_CODES = {
    "logistic_regression": "lr",
    "random_forest": "rf",
    "xgboost": "xgb",
}

# Models whose mean CV ROC AUC is less than this below the best one are tied; among them the
# higher mean CV recall (class 1) wins. Used by ml.train and shown on the comparison page.
CHAMPION_AUC_MARGIN = 0.01


def model_version_tag(model_name, version):
    """Return the value stored in credit_applications.model_version, e.g. ``lr@2026-11-13.1``."""
    return f"{MODEL_CODES[model_name]}@{version}"


def parse_model_version_tag(tag):
    """Split a stored ``model_version`` into ``(model name, version)``.

    Returns ``(None, None)`` when the value is empty or does not have the ``code@version`` format
    (evaluations made before the trained models existed have no model version).
    """
    code, separator, version = (tag or "").partition("@")
    names = {value: name for name, value in MODEL_CODES.items()}
    if not separator or code not in names:
        return None, None
    return names[code], version


CV_METRICS = ("roc_auc", "recall", "precision", "f1")
TEST_METRICS = ("roc_auc", "recall", "precision", "f1", "accuracy")

MANIFEST_KEYS = ("version", "trained_at", "dataset", "feature_set", "selection_rule", "champion", "models")
# Written by real training runs; the fictitious example manifest may omit them.
MANIFEST_OPTIONAL_KEYS = ("success_criteria",)
DATASET_KEYS = ("name", "sha256", "rows")
DATASET_OPTIONAL_KEYS = ("expected_sha256", "sha256_matches_expected")

# Extra artifacts of a real training run, next to manifest.json.
DATA_REPORT_FILENAME = "data_report.json"
EXPERIMENTS_FILENAME = "experiments.json"
OVERFITTING_FILENAME = "overfitting.json"
SUBGROUPS_FILENAME = "subgroups.json"
# Written by notebooks/credit_risk_dimensionality.ipynb, not by ml.train.
DIMENSIONALITY_REPORT_FILENAME = "dimensionality_report.json"
# Written by ml.monitor: the train distribution used as reference, and the report of a batch.
REFERENCE_DISTRIBUTION_FILENAME = "reference_distribution.json"
MONITORING_REPORT_FILENAME = "monitoring_report.json"

# Monitoring: PSI below PSI_STABLE is stable, up to PSI_ALERT is "watch", above is an alert.
PSI_STABLE = 0.1
PSI_ALERT = 0.25
RISK_LABELS = ("Approved", "Medium Risk", "High Risk")
PSI_STATUSES = ("stable", "watch", "alert")

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


def _check_keys(doc, expected, where, optional=()):
    if not isinstance(doc, dict):
        return [f"{where} must be an object"]
    errors = [f"{where} is missing '{key}'" for key in expected if key not in doc]
    errors += [
        f"{where} has unexpected key '{key}'"
        for key in doc
        if key not in expected and key not in optional
    ]
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
    errors = _check_keys(manifest, MANIFEST_KEYS, "manifest", MANIFEST_OPTIONAL_KEYS)
    if not isinstance(manifest, dict):
        return errors

    if not isinstance(manifest.get("version"), str) or not manifest.get("version"):
        errors.append("manifest.version must be a non-empty string")
    if not isinstance(manifest.get("trained_at"), str) or not _ISO_UTC.fullmatch(manifest["trained_at"]):
        errors.append("manifest.trained_at must be an ISO 8601 UTC timestamp such as 2026-11-10T21:30:00Z")

    dataset = manifest.get("dataset")
    dataset_errors = _check_keys(dataset, DATASET_KEYS, "manifest.dataset", DATASET_OPTIONAL_KEYS)
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

    criteria = manifest.get("success_criteria")
    if criteria is not None:
        errors += _check_success_criteria(criteria)
    return errors


def _check_success_criteria(criteria):
    """success_criteria: {"champion": str, "all_passed": bool, "results": [{criterion, threshold, value, passed}]}."""
    errors = _check_keys(criteria, ("champion", "all_passed", "results"), "manifest.success_criteria")
    if errors:
        return errors
    if not isinstance(criteria["all_passed"], bool):
        errors.append("manifest.success_criteria.all_passed must be a boolean")
    results = criteria["results"]
    if not isinstance(results, list) or not results:
        return errors + ["manifest.success_criteria.results must be a non-empty list"]
    for item in results:
        if not (isinstance(item, dict) and set(item) == {"criterion", "threshold", "value", "passed"}
                and isinstance(item["criterion"], str) and _is_number(item["value"])
                and isinstance(item["passed"], bool)):
            errors.append("manifest.success_criteria.results items need criterion, threshold, value and passed")
            break
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


def validate_data_report(report):
    """Validate data_report.json: before/after statistics, transformations and split sizes."""
    errors = _check_keys(report, ("dataset", "before", "after", "transformations", "split"), "data_report")
    if errors:
        return errors
    keys = ("rows", "columns", "null_cells", "null_by_column", "duplicate_rows", "duplicate_ids",
            "default_rate", "inconsistencies", "outliers")
    for part in ("before", "after"):
        errors += _check_keys(report[part], keys, f"data_report.{part}")
    if not isinstance(report["transformations"], list) or not report["transformations"]:
        errors.append("data_report.transformations must be a non-empty list")
    return errors


def validate_experiments(experiments):
    """Validate experiments.json: the protocol and every hyperparameter run of every model."""
    errors = _check_keys(experiments, ("version", "trained_at", "protocol", "total_seconds", "models"), "experiments")
    if errors:
        return errors
    errors += _check_keys(
        experiments["protocol"],
        ("selection_data", "test_usage", "scoring", "cv_folds", "random_state", "search"),
        "experiments.protocol",
    )
    models = experiments["models"]
    if not isinstance(models, dict) or not models:
        return errors + ["experiments.models must be a non-empty object"]
    for name, entry in models.items():
        where = f"experiments.models[{name!r}]"
        keys = ("search_space", "n_candidates", "search_seconds", "runs")
        errors += _check_keys(entry, keys, where)
        if not isinstance(entry, dict) or not isinstance(entry.get("runs"), list) or not entry["runs"]:
            errors.append(f"{where}.runs must be a non-empty list")
            continue
        if any(not (isinstance(run, dict) and set(run) == {"run", "params", "cv", "fit_seconds", "selected"})
               for run in entry["runs"]):
            errors.append(f"{where}.runs items need run, params, cv, fit_seconds and selected")
        elif sum(1 for run in entry["runs"] if run["selected"] is True) != 1:
            errors.append(f"{where} must have exactly one selected run")
    return errors


def validate_overfitting(overfitting):
    """Validate overfitting.json: train vs. CV vs. test ROC AUC per model."""
    errors = _check_keys(overfitting, ("version", "threshold", "models"), "overfitting")
    if errors:
        return errors
    models = overfitting["models"]
    if not isinstance(models, dict) or not models:
        return ["overfitting.models must be a non-empty object"]
    keys = ("train_roc_auc", "cv_roc_auc", "test_roc_auc", "train_minus_cv", "cv_minus_test", "overfit")
    for name, entry in models.items():
        where = f"overfitting.models[{name!r}]"
        errors += _check_keys(entry, keys, where)
        if isinstance(entry, dict) and not isinstance(entry.get("overfit"), bool):
            errors.append(f"{where}.overfit must be a boolean")
    return errors


def validate_subgroups(subgroups):
    """Validate subgroups.json: test metrics by age range and employment type per model."""
    errors = _check_keys(subgroups, ("version", "split", "models"), "subgroups", ("findings",))
    if errors:
        return errors
    findings = subgroups.get("findings")
    if findings is not None:
        finding_keys = ("id", "dimension", "model", "severity", "title", "summary", "evidence", "recommendation")
        if not isinstance(findings, list) or not findings:
            errors.append("subgroups.findings must be a non-empty list")
        else:
            for item in findings:
                errors += _check_keys(item, finding_keys, "subgroups.findings item")
    models = subgroups["models"]
    if not isinstance(models, dict) or not models:
        return ["subgroups.models must be a non-empty object"]
    for name, entry in models.items():
        errors += _check_keys(entry, ("age_range", "employment_type"), f"subgroups.models[{name!r}]")
    return errors


def validate_dimensionality_report(report):
    """Validate dimensionality_report.json (written by the dimensionality notebook).

    Format::

        {
          "artifacts_version": "2026-11-13.1",   # manifest.version of the champion it was run with
          "champion": "logistic_regression",
          "dataset": {"sha256": "<64 hex>", "train_rows": int},
          "protocol": {"data": str, "cv_folds": 5, "random_state": 42, "test_usage": str},
          "pca": {"input_columns": [...], "explained_variance_ratio": [...], "cumulative_variance": [...],
                  "components_for_90_percent": int, "components_for_95_percent": int},
          "tsne": {"sample_rows": int, "perplexity": number, "random_state": int, "kl_divergence": number},
          "experiments": {
            "pca_components": {"baseline": {"n_features": int, "cv": {"roc_auc": [m, s], "recall": [m, s]}},
                               "variants": [{"n_components": int, "explained_variance": number,
                                             "cv": {...}, "delta_roc_auc": number, "delta_recall": number}]},
            "without_age": {"with_age": {"cv": {...}, "flagged_rate": number},
                            "without_age": {"cv": {...}, "flagged_rate": number},
                            "by_age_range": {label: {"rows", "default_rate", "flagged_rate_with_age",
                                                      "flagged_rate_without_age", "recall_with_age",
                                                      "recall_without_age"}},
                            "flag_rate_ratio_youngest_to_oldest": {"with_age": x, "without_age": x}}
          },
          "interpretation": [str, ...],
          "figures": ["methodology/pca_scree.png", ...]
        }
    """
    top = ("artifacts_version", "champion", "dataset", "protocol", "pca", "tsne", "experiments",
           "interpretation", "figures")
    errors = _check_keys(report, top, "dimensionality_report")
    if errors:
        return errors

    if report["champion"] not in MODEL_NAMES:
        errors.append("dimensionality_report.champion must be one of the model names")
    errors += _check_keys(report["dataset"], ("sha256", "train_rows"), "dimensionality_report.dataset")
    errors += _check_keys(report["protocol"], ("data", "cv_folds", "random_state", "test_usage"),
                          "dimensionality_report.protocol")
    errors += _check_keys(
        report["pca"],
        ("input_columns", "explained_variance_ratio", "cumulative_variance",
         "components_for_90_percent", "components_for_95_percent"),
        "dimensionality_report.pca",
    )
    errors += _check_keys(report["tsne"], ("sample_rows", "perplexity", "random_state", "kl_divergence"),
                          "dimensionality_report.tsne")

    experiments = report["experiments"]
    errors += _check_keys(experiments, ("pca_components", "without_age"), "dimensionality_report.experiments")
    if errors:
        return errors

    pca_experiment = experiments["pca_components"]
    errors += _check_keys(pca_experiment, ("baseline", "variants"), "experiments.pca_components")
    if isinstance(pca_experiment.get("variants"), list) and pca_experiment["variants"]:
        for variant in pca_experiment["variants"]:
            keys = ("n_components", "explained_variance", "cv", "delta_roc_auc", "delta_recall")
            errors += _check_keys(variant, keys, "experiments.pca_components.variants item")
    else:
        errors.append("experiments.pca_components.variants must be a non-empty list")

    without_age = experiments["without_age"]
    errors += _check_keys(
        without_age,
        ("with_age", "without_age", "by_age_range", "flag_rate_ratio_youngest_to_oldest"),
        "experiments.without_age",
    )
    by_age = without_age.get("by_age_range") if isinstance(without_age, dict) else None
    if not isinstance(by_age, dict) or not by_age:
        errors.append("experiments.without_age.by_age_range must be a non-empty object")
    else:
        keys = ("rows", "default_rate", "flagged_rate_with_age", "flagged_rate_without_age",
                "recall_with_age", "recall_without_age")
        for label, group in by_age.items():
            errors += _check_keys(group, keys, f"experiments.without_age.by_age_range[{label!r}]")

    if not isinstance(report["interpretation"], list) or not report["interpretation"]:
        errors.append("dimensionality_report.interpretation must be a non-empty list")
    if not isinstance(report["figures"], list) or not report["figures"]:
        errors.append("dimensionality_report.figures must be a non-empty list")
    return errors


def psi_status(value):
    """Status of a PSI value: ``stable`` (< 0.1), ``watch`` (0.1 to 0.25) or ``alert`` (> 0.25)."""
    if value < PSI_STABLE:
        return "stable"
    return "watch" if value <= PSI_ALERT else "alert"


def validate_reference_distribution(reference):
    """Validate reference_distribution.json: statistics of the train split used as PSI reference.

    Format::

        {
          "version": "2026-11-13.1", "feature_set": "v2-loan-default",
          "dataset": {"sha256": "<64 hex>", "train_rows": int},
          "bins": 10,
          "numeric": {"Age": {"cuts": [...], "fractions": [...], "min": x, "max": x, "mean": x, "integer": bool}},
          "categorical": {"EmploymentType": {"Full-time": 0.25, ...}},
          "labels": {"model": "logistic_regression", "thresholds": {...}, "rates": {"Approved": x, ...},
                     "mean_risk": x},
          "note": "..."
        }

    Only statistics: there are no rows of the dataset.
    """
    keys = ("version", "feature_set", "dataset", "bins", "numeric", "categorical", "labels", "note")
    errors = _check_keys(reference, keys, "reference")
    if errors:
        return errors
    errors += _check_keys(reference["dataset"], ("sha256", "train_rows"), "reference.dataset")
    if reference["feature_set"] not in FEATURE_SETS:
        errors.append("reference.feature_set must be one of the feature sets")
    numeric = reference["numeric"]
    if not isinstance(numeric, dict) or not numeric:
        return errors + ["reference.numeric must be a non-empty object"]
    for name, item in numeric.items():
        where = f"reference.numeric[{name!r}]"
        errors += _check_keys(item, ("cuts", "fractions", "min", "max", "mean", "integer"), where)
        if isinstance(item, dict) and isinstance(item.get("cuts"), list) and isinstance(item.get("fractions"), list):
            if len(item["fractions"]) != len(item["cuts"]) + 1:
                errors.append(f"{where}.fractions must have one more value than cuts")
            elif abs(sum(item["fractions"]) - 1) > 1e-3:
                errors.append(f"{where}.fractions must add up to 1")
            if item["cuts"] != sorted(item["cuts"]):
                errors.append(f"{where}.cuts must be sorted")
    for name, fractions in reference["categorical"].items():
        if not isinstance(fractions, dict) or abs(sum(fractions.values()) - 1) > 1e-3:
            errors.append(f"reference.categorical[{name!r}] must be fractions that add up to 1")
    labels = reference["labels"]
    errors += _check_keys(labels, ("model", "thresholds", "rates", "mean_risk"), "reference.labels")
    if isinstance(labels, dict) and isinstance(labels.get("rates"), dict):
        if set(labels["rates"]) != set(RISK_LABELS) or abs(sum(labels["rates"].values()) - 1) > 1e-3:
            errors.append("reference.labels.rates must have the three risk labels and add up to 1")
    return errors


def validate_monitoring_report(report):
    """Validate monitoring_report.json: PSI per feature and label rates of a batch against train.

    ``source`` is ``SIMULATED`` for the generated batch (``simulated`` is then true and
    ``batch.drift_injected`` lists the drift put on purpose) or ``PREDICTION_LOG`` for a real log.
    """
    keys = ("generated_at", "source", "simulated", "model", "artifacts_version", "reference", "batch",
            "thresholds", "psi", "overall_status", "features_in_alert", "features_to_watch", "labels",
            "risk", "recommendation")
    errors = _check_keys(report, keys, "monitoring_report")
    if errors:
        return errors
    if report["source"] not in ("SIMULATED", "PREDICTION_LOG"):
        errors.append("monitoring_report.source must be SIMULATED or PREDICTION_LOG")
    if report["simulated"] != (report["source"] == "SIMULATED"):
        errors.append("monitoring_report.simulated must be true exactly when source is SIMULATED")
    if not isinstance(report["generated_at"], str) or not _ISO_UTC.fullmatch(report["generated_at"]):
        errors.append("monitoring_report.generated_at must be an ISO 8601 UTC timestamp")
    errors += _check_keys(report["reference"], ("rows", "dataset_sha256"), "monitoring_report.reference")
    batch = report["batch"]
    errors += _check_keys(batch, ("rows", "seed", "period", "drift_injected"), "monitoring_report.batch")
    if isinstance(batch, dict) and report["simulated"] and not batch.get("drift_injected"):
        errors.append("a SIMULATED report must list the drift it injected")
    errors += _check_keys(report["thresholds"], ("stable_below", "alert_above"), "monitoring_report.thresholds")
    psi = report["psi"]
    if not isinstance(psi, dict) or not psi:
        return errors + ["monitoring_report.psi must be a non-empty object"]
    for name, item in psi.items():
        where = f"monitoring_report.psi[{name!r}]"
        errors += _check_keys(item, ("value", "status"), where)
        if isinstance(item, dict) and _is_number(item.get("value")):
            if item.get("status") != psi_status(item["value"]):
                errors.append(f"{where}.status does not match the value and the thresholds")
        else:
            errors.append(f"{where}.value must be a number")
    if report["overall_status"] not in PSI_STATUSES:
        errors.append("monitoring_report.overall_status must be stable, watch or alert")
    errors += _check_keys(report["labels"], ("reference", "batch", "difference"), "monitoring_report.labels")
    errors += _check_keys(report["risk"], ("reference_mean", "batch_mean"), "monitoring_report.risk")
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

    extra_validators = (
        (DATA_REPORT_FILENAME, validate_data_report),
        (EXPERIMENTS_FILENAME, validate_experiments),
        (OVERFITTING_FILENAME, validate_overfitting),
        (SUBGROUPS_FILENAME, validate_subgroups),
    )
    for filename, validator in extra_validators:
        path = os.path.join(directory, filename)
        if os.path.exists(path):
            errors += [f"{filename}: {error}" for error in validator(load_json(path))]
        elif require_models:
            errors.append(f"{path} does not exist")

    # Optional: produced by the notebook and by ml.monitor, validated when present.
    optional = (
        (DIMENSIONALITY_REPORT_FILENAME, validate_dimensionality_report),
        (REFERENCE_DISTRIBUTION_FILENAME, validate_reference_distribution),
        (MONITORING_REPORT_FILENAME, validate_monitoring_report),
    )
    for filename, validator in optional:
        path = os.path.join(directory, filename)
        if os.path.exists(path):
            errors += [f"{filename}: {error}" for error in validator(load_json(path))]

    if require_models and artifacts_size(directory) >= MAX_ARTIFACTS_BYTES:
        errors.append(f"{directory} is {artifacts_size(directory)} bytes; the limit is {MAX_ARTIFACTS_BYTES}")
    return errors
