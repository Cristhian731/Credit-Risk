"""Compute the test-set metrics of a fitted model.

Owner: data (Sprint 1). ml.train merges the output into each model's
metrics.json; ml.schemas defines the exact format.
"""
THRESHOLD = 0.5
ROC_POINTS = 50


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
    raise NotImplementedError("Sprint 1 - owner: data")
