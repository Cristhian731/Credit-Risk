"""Build the scikit-learn pipelines of the three candidate models.

Owner: ml (Sprint 1). Model names and display names live in ml.schemas.
"""
from ml.features import DEFAULT_FEATURE_SET


def build_pipeline(name, feature_set=DEFAULT_FEATURE_SET, scale_pos_weight=None):
    """Return an unfitted pipeline (preprocessing + classifier) for one model.

    Every pipeline selects ``FEATURE_SETS[feature_set]["columns"]``, one-hot
    encodes the categorical ones (unknown categories ignored) and exposes
    ``predict_proba`` with class 1 = default.

    Models and class imbalance:
        - ``logistic_regression``: numeric columns scaled with
          ``StandardScaler``; ``class_weight="balanced"``.
        - ``random_forest``: ``class_weight="balanced"``. Limit ``max_depth``,
          ``min_samples_leaf`` and ``n_estimators`` so the three saved models
          stay under 20 MB in total.
        - ``xgboost``: ``XGBClassifier`` with ``scale_pos_weight`` =
          negatives / positives of the training labels.

    Args:
        name: One of ``ml.schemas.MODEL_NAMES``.
        feature_set: A key of ``ml.features.FEATURE_SETS``.
        scale_pos_weight: Only used by ``xgboost``; computed by the caller
            from the training labels.

    Returns:
        An unfitted ``sklearn.pipeline.Pipeline``.

    Raises:
        ValueError: If ``name`` or ``feature_set`` is unknown.
    """
    raise NotImplementedError("Sprint 1 - owner: ml")
