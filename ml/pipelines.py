

"""Build the scikit-learn pipelines of the three candidate models.

Owner: ml (Sprint 1). Model names and display names live in ml.schemas.
"""

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from ml.features import DEFAULT_FEATURE_SET, FEATURE_SETS
from ml.schemas import MODEL_NAMES


def build_pipeline(name, feature_set=DEFAULT_FEATURE_SET, scale_pos_weight=None):
    """Return an unfitted pipeline for the requested model."""

    if name not in MODEL_NAMES:
        raise ValueError(f"Unknown model: {name}")

    if feature_set not in FEATURE_SETS:
        raise ValueError(f"Unknown feature set: {feature_set}")

    if name != "xgboost":
        raise NotImplementedError(
            f"The {name} pipeline is not implemented in this branch."
        )

    if scale_pos_weight is None or scale_pos_weight <= 0:
        raise ValueError("XGBoost requires a positive scale_pos_weight.")

    feature_config = FEATURE_SETS[feature_set]
    columns = list(feature_config["columns"])
    categorical_columns = list(feature_config["categorical"])
    numeric_columns = [
        column for column in columns
        if column not in categorical_columns
    ]

    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    preprocessing = ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, numeric_columns),
            ("categorical", categorical_pipeline, categorical_columns),
        ],
        remainder="drop",
    )

    classifier = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=scale_pos_weight,
        n_estimators=150,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=1,
        tree_method="hist",
    )

    return Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            ("classifier", classifier),
        ]
    )
