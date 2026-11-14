"""Build the scikit-learn pipelines of the three candidate models.

Model names and display names live in ml.schemas. Every pipeline is a single
object (preprocessing + classifier) that takes the raw feature columns of the
feature set and exposes ``predict_proba`` (class 1 = default).
"""

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from ml.features import DEFAULT_FEATURE_SET, FEATURE_SETS
from ml.schemas import MODEL_NAMES

RANDOM_STATE = 42

# Hyperparameter search spaces (small on purpose: the whole training must stay
# under 30 minutes and the artifacts under 20 MB). Keys are Pipeline parameters.
SEARCH_SPACES = {
    "logistic_regression": {
        "classifier__C": [0.01, 0.1, 1.0, 10.0],
    },
    "random_forest": {
        "classifier__n_estimators": [100, 150],
        "classifier__max_depth": [6, 8, 10],
        "classifier__min_samples_leaf": [100, 300, 600],
        "classifier__max_features": ["sqrt", 0.5],
    },
    "xgboost": {
        "classifier__n_estimators": [150, 300],
        "classifier__max_depth": [3, 4, 6],
        "classifier__learning_rate": [0.03, 0.05, 0.1],
        "classifier__subsample": [0.8, 1.0],
        "classifier__colsample_bytree": [0.8, 1.0],
        "classifier__min_child_weight": [1, 5],
    },
}


def _preprocessing(feature_set, scale_numeric):
    feature_config = FEATURE_SETS[feature_set]
    columns = list(feature_config["columns"])
    categorical_columns = list(feature_config["categorical"])
    numeric_columns = [column for column in columns if column not in categorical_columns]

    numeric_steps = [("imputer", SimpleImputer(strategy="median"))]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("numeric", Pipeline(steps=numeric_steps), numeric_columns),
            ("categorical", categorical_pipeline, categorical_columns),
        ],
        remainder="drop",
    )


def build_pipeline(name, feature_set=DEFAULT_FEATURE_SET, scale_pos_weight=None):
    """Return an unfitted pipeline for the requested model.

    Args:
        name: One of ``ml.schemas.MODEL_NAMES``.
        feature_set: A key of ``ml.features.FEATURE_SETS``.
        scale_pos_weight: Negatives / positives of the training labels.
            Required (> 0) for ``xgboost``; the other models use
            ``class_weight="balanced"``.
    """

    if name not in MODEL_NAMES:
        raise ValueError(f"Unknown model: {name}")

    if feature_set not in FEATURE_SETS:
        raise ValueError(f"Unknown feature set: {feature_set}")

    if name == "logistic_regression":
        classifier = LogisticRegression(
            C=1.0,
            class_weight="balanced",
            max_iter=1000,
            random_state=RANDOM_STATE,
        )
    elif name == "random_forest":
        # Adapted from the baseline script (ml/experiments/random_forest_baseline.py),
        # with shallower trees and larger leaves so the saved model stays small.
        classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            min_samples_leaf=300,
            max_features="sqrt",
            class_weight="balanced",
            n_jobs=1,
            random_state=RANDOM_STATE,
        )
    else:
        if scale_pos_weight is None or scale_pos_weight <= 0:
            raise ValueError("XGBoost requires a positive scale_pos_weight.")
        classifier = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            scale_pos_weight=scale_pos_weight,
            n_estimators=150,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=RANDOM_STATE,
            n_jobs=1,
            tree_method="hist",
        )

    return Pipeline(
        steps=[
            ("preprocessing", _preprocessing(feature_set, scale_numeric=name == "logistic_regression")),
            ("classifier", classifier),
        ]
    )
