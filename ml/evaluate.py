"""Compute the test-set metrics of a fitted model.

ml.train merges the output of ``evaluate`` into each model's metrics.json;
ml.schemas defines the exact format. The held-out test split is evaluated
once per model, after the hyperparameters and the champion were chosen with
cross-validation on the train split.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

THRESHOLD = 0.5
ROC_POINTS = 50

AGE_BINS = (17, 24, 34, 44, 54, 69)
AGE_LABELS = ("18-24", "25-34", "35-44", "45-54", "55-69")
MIN_GROUP_ROWS = 30


def _probabilities(model, X):
    return np.asarray(model.predict_proba(X))[:, 1]


def _scores(y, proba):
    """Class 1 metrics at THRESHOLD, as plain floats."""
    y = np.asarray(y)
    pred = (proba >= THRESHOLD).astype(int)
    return {
        "roc_auc": float(roc_auc_score(y, proba)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "accuracy": float((pred == y).mean()),
    }


def evaluate(model, X, y):
    """Evaluate a fitted model on the held-out test set.

    Args:
        model: A fitted pipeline exposing ``predict_proba`` (class 1 = default).
        X: Test features, as returned by ``ml.dataset.split``.
        y: Test labels (0/1).

    Returns:
        A dict with exactly the keys ``ml.schemas.EVALUATION_KEYS`` of
        metrics.json, no more and no fewer:

        - ``test``: ``{"roc_auc", "recall", "precision", "f1", "accuracy"}``,
          floats in [0, 1]; recall, precision and f1 refer to class 1 and use
          ``THRESHOLD`` on the predicted probability.
        - ``confusion_matrix``: ``[[tn, fp], [fn, tp]]`` (integers, same
          threshold); its total equals ``len(y)``.
        - ``roc_curve``: ``{"fpr": [...], "tpr": [...]}`` downsampled to about
          ``ROC_POINTS`` points, non-decreasing, from (0, 0) to (1, 1).

        The other keys of metrics.json (``model``, ``display_name``,
        ``model_version``, ``cv``, ``feature_importance``, ``params``) are
        added by ``ml.train``.
    """
    y = np.asarray(y)
    proba = _probabilities(model, X)
    pred = (proba >= THRESHOLD).astype(int)

    matrix = confusion_matrix(y, pred, labels=[0, 1])

    fpr, tpr, _thresholds = roc_curve(y, proba)
    keep = np.unique(np.linspace(0, len(fpr) - 1, ROC_POINTS).round().astype(int))
    return {
        "test": _scores(y, proba),
        "confusion_matrix": [[int(v) for v in row] for row in matrix],
        "roc_curve": {
            "fpr": [round(float(v), 4) for v in fpr[keep]],
            "tpr": [round(float(v), 4) for v in tpr[keep]],
        },
    }


def evaluate_subgroups(model, X, y):
    """Metrics of a fitted model per subgroup of the test set (statistics only).

    Groups: age ranges and ``EmploymentType``. Groups smaller than
    ``MIN_GROUP_ROWS`` are reported without metrics. This is a fairness
    check; it is never used to tune or select a model.

    Returns:
        ``{"age_range": {label: stats}, "employment_type": {label: stats}}``
        where ``stats`` has ``rows``, ``default_rate``, ``predicted_default_rate``
        and, when the group is large enough and has both classes, ``roc_auc``,
        ``recall`` and ``precision``.
    """
    y = np.asarray(y)
    proba = _probabilities(model, X)
    pred = (proba >= THRESHOLD).astype(int)

    age_group = pd.cut(X["Age"].to_numpy(), bins=list(AGE_BINS), labels=list(AGE_LABELS))
    groups = {
        "age_range": pd.Series(age_group.astype(str), index=range(len(y))),
        "employment_type": pd.Series(X["EmploymentType"].astype(str).to_numpy(), index=range(len(y))),
    }

    result = {}
    for dimension, labels in groups.items():
        result[dimension] = {}
        for label in sorted(labels.unique()):
            mask = (labels == label).to_numpy()
            stats = {
                "rows": int(mask.sum()),
                "default_rate": round(float(y[mask].mean()), 4),
                "predicted_default_rate": round(float(pred[mask].mean()), 4),
            }
            if mask.sum() >= MIN_GROUP_ROWS and len(set(y[mask])) == 2:
                stats["roc_auc"] = round(float(roc_auc_score(y[mask], proba[mask])), 4)
                stats["recall"] = round(float(recall_score(y[mask], pred[mask], zero_division=0)), 4)
                stats["precision"] = round(float(precision_score(y[mask], pred[mask], zero_division=0)), 4)
            result[dimension][label] = stats
    return result
