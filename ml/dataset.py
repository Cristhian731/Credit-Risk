"""Load, clean and split the Loan Default Prediction Dataset.

See ml/data/README.md for the download and the checksum, and
docs/ML_PHASE.md for the contracts.
"""
import hashlib
import os
import warnings

import pandas as pd
from sklearn.model_selection import train_test_split

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DEFAULT_DATA_PATH = os.path.join(DATA_DIR, "raw", "Loan_default.csv")

ID_COLUMN = "LoanID"
TARGET_COLUMN = "Default"

# The 18 columns of Loan_default.csv, in file order.
RAW_COLUMNS = (
    "LoanID",
    "Age",
    "Income",
    "LoanAmount",
    "CreditScore",
    "MonthsEmployed",
    "NumCreditLines",
    "InterestRate",
    "LoanTerm",
    "DTIRatio",
    "Education",
    "EmploymentType",
    "MaritalStatus",
    "HasMortgage",
    "HasDependents",
    "LoanPurpose",
    "HasCoSigner",
    "Default",
)

NUMERIC_COLUMNS = (
    "Age", "Income", "LoanAmount", "CreditScore", "MonthsEmployed",
    "NumCreditLines", "InterestRate", "LoanTerm", "DTIRatio",
)
CATEGORICAL_COLUMNS = (
    "Education", "EmploymentType", "MaritalStatus", "HasMortgage",
    "HasDependents", "LoanPurpose", "HasCoSigner",
)

# SHA-256 of the file the models were developed with. A different hash only
# triggers a warning (Windows line endings, for instance, change it).
EXPECTED_SHA256 = "1d7556a9071e7f9e872dc05a0cad174229fb1164b1cf3470ad35eed195c24278"

TEST_SIZE = 0.2
RANDOM_STATE = 42


def file_sha256(path):
    """Return the SHA-256 of a file as 64 lowercase hexadecimal characters."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path=DEFAULT_DATA_PATH):
    """Read the dataset CSV and check its shape.

    The SHA-256 of the file is stored in ``df.attrs["sha256"]``. If it differs
    from ``EXPECTED_SHA256`` a ``UserWarning`` is emitted, but loading goes on.

    Args:
        path: Path to ``Loan_default.csv`` (or a file with the same columns,
            such as ``tests/fixtures/loan_default_sample.csv``).

    Returns:
        A ``pandas.DataFrame`` with exactly ``RAW_COLUMNS``, in that order,
        and ``TARGET_COLUMN`` as integers 0/1 (1 = default).

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If a column is missing or extra, the target has values
            other than 0/1, or there are missing values.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found: {path}")

    sha256 = file_sha256(path)
    if sha256 != EXPECTED_SHA256:
        warnings.warn(
            f"Dataset SHA-256 {sha256} differs from the expected {EXPECTED_SHA256}; "
            "results may not be reproducible (check line endings and the file version).",
            UserWarning,
            stacklevel=2,
        )

    df = pd.read_csv(path)

    missing = [column for column in RAW_COLUMNS if column not in df.columns]
    extra = [column for column in df.columns if column not in RAW_COLUMNS]
    if missing or extra:
        raise ValueError(f"Unexpected columns. Missing: {missing}. Extra: {extra}.")

    null_columns = [column for column in RAW_COLUMNS if df[column].isna().any()]
    if null_columns:
        raise ValueError(f"Missing values in columns: {null_columns}")

    if not set(df[TARGET_COLUMN].unique()) <= {0, 1}:
        raise ValueError(f"{TARGET_COLUMN} must contain only 0 and 1")

    df = df[list(RAW_COLUMNS)].copy()
    df[TARGET_COLUMN] = df[TARGET_COLUMN].astype(int)
    df.attrs["sha256"] = sha256
    return df


def split(df):
    """Split into a stratified train set and a held-out test set.

    The test set (``TEST_SIZE`` = 20 %, ``RANDOM_STATE`` = 42, stratified on
    ``TARGET_COLUMN``) is only used to report final metrics, never to select
    or tune a model.

    Args:
        df: The frame returned by :func:`load`.

    Returns:
        ``(X_train, X_test, y_train, y_test)``. ``X_*`` keep every column
        except ``ID_COLUMN`` and ``TARGET_COLUMN``; ``y_*`` are integer Series.
        The same input always gives the same split.
    """
    X = df.drop(columns=[ID_COLUMN, TARGET_COLUMN])
    y = df[TARGET_COLUMN].astype(int)
    return train_test_split(
        X, y, test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE
    )


# ---------------------------------------------------------------------------
# Data quality report (data_report.json): statistics only, never raw rows.
# ---------------------------------------------------------------------------

def clean(df):
    """Apply the row-level cleaning used before training.

    Strips whitespace from the categorical columns and removes exact duplicate
    rows and repeated ``LoanID`` values (keeping the first one). Outliers are
    NOT removed: they are real applicants, trees are insensitive to scale and
    the logistic regression standardizes its inputs.
    """
    cleaned = df.copy()
    for column in CATEGORICAL_COLUMNS:
        cleaned[column] = cleaned[column].astype(str).str.strip()
    cleaned = cleaned.drop_duplicates().drop_duplicates(subset=[ID_COLUMN])
    cleaned.attrs.update(df.attrs)
    return cleaned


def _inconsistencies(df):
    """Count rows that break a basic domain rule (one count per rule)."""
    checks = {
        "age_outside_18_100": (df["Age"] < 18) | (df["Age"] > 100),
        "income_not_positive": df["Income"] <= 0,
        "loan_amount_not_positive": df["LoanAmount"] <= 0,
        "credit_score_outside_300_850": (df["CreditScore"] < 300) | (df["CreditScore"] > 850),
        "months_employed_negative": df["MonthsEmployed"] < 0,
        "months_employed_exceed_adult_life": df["MonthsEmployed"] > (df["Age"] - 16) * 12,
        "num_credit_lines_negative": df["NumCreditLines"] < 0,
        "interest_rate_outside_0_100": (df["InterestRate"] < 0) | (df["InterestRate"] > 100),
        "loan_term_not_positive": df["LoanTerm"] <= 0,
        "dti_ratio_outside_0_1": (df["DTIRatio"] < 0) | (df["DTIRatio"] > 1),
        "target_not_0_1": ~df[TARGET_COLUMN].isin([0, 1]),
    }
    counts = {name: int(mask.sum()) for name, mask in checks.items()}
    counts["categorical_with_surrounding_spaces"] = int(sum(
        (df[column].astype(str) != df[column].astype(str).str.strip()).sum()
        for column in CATEGORICAL_COLUMNS
    ))
    return counts


def _outliers(df):
    """IQR rule (1.5 x IQR) per numeric column: summary, bounds and counts."""
    result = {}
    for column in NUMERIC_COLUMNS:
        q1, q3 = df[column].quantile([0.25, 0.75])
        iqr = q3 - q1
        lower, upper = float(q1 - 1.5 * iqr), float(q3 + 1.5 * iqr)
        count = int(((df[column] < lower) | (df[column] > upper)).sum())
        result[column] = {
            "min": float(df[column].min()),
            "median": float(df[column].median()),
            "max": float(df[column].max()),
            "lower_bound": round(lower, 4),
            "upper_bound": round(upper, 4),
            "outliers": count,
            "outlier_percent": round(100 * count / len(df), 4),
        }
    return result


def _snapshot(df):
    nulls = {column: int(count) for column, count in df.isna().sum().items() if count}
    return {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "null_cells": int(sum(nulls.values())),
        "null_by_column": nulls,
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_ids": int(df[ID_COLUMN].duplicated().sum()),
        "default_rate": round(float(df[TARGET_COLUMN].mean()), 6),
        "inconsistencies": _inconsistencies(df),
        "outliers": _outliers(df),
    }


def build_data_report(raw, cleaned, y_train, y_test):
    """Build the content of data_report.json (statistics only, no raw rows).

    Args:
        raw: Frame returned by :func:`load`.
        cleaned: Frame returned by :func:`clean` (the one that gets split).
        y_train, y_test: Labels returned by :func:`split`.
    """
    sha256 = raw.attrs.get("sha256")
    return {
        "dataset": {
            "name": "Loan Default Prediction Dataset",
            "sha256": sha256,
            "expected_sha256": EXPECTED_SHA256,
            "sha256_matches_expected": sha256 == EXPECTED_SHA256,
        },
        "before": _snapshot(raw),
        "after": _snapshot(cleaned),
        "transformations": [
            {"step": "drop_identifier", "columns": [ID_COLUMN],
             "detail": "LoanID has no predictive signal."},
            {"step": "drop_duplicates", "columns": ["all"],
             "detail": "Exact duplicate rows and repeated LoanID values are removed; "
                       "before.rows minus after.rows is the number removed."},
            {"step": "strip_categorical_whitespace", "columns": list(CATEGORICAL_COLUMNS),
             "detail": "Removes leading and trailing spaces."},
            {"step": "median_imputation", "columns": ["numeric model columns"],
             "detail": "Safety net inside the pipeline; the dataset has no nulls."},
            {"step": "most_frequent_imputation", "columns": ["categorical model columns"],
             "detail": "Safety net inside the pipeline; the dataset has no nulls."},
            {"step": "one_hot_encoding", "columns": ["EmploymentType"],
             "detail": "Unknown categories are ignored at prediction time."},
            {"step": "standard_scaling", "columns": ["numeric model columns"],
             "detail": "Logistic regression only; trees do not need scaling."},
            {"step": "outliers_kept", "columns": list(NUMERIC_COLUMNS),
             "detail": "Outliers (IQR rule) are real applicants and are not removed."},
            {"step": "income_is_annual", "columns": ["Income"],
             "detail": "Income goes from 15,000 to 149,999 with a median near 82,000, so it is annual. "
                       "The form asks for monthly income and to_model_frame multiplies it by 12."},
        ],
        "split": {
            "test_size": TEST_SIZE,
            "random_state": RANDOM_STATE,
            "stratified_on": TARGET_COLUMN,
            "train_rows": int(len(y_train)),
            "test_rows": int(len(y_test)),
            "train_default_rate": round(float(y_train.mean()), 6),
            "test_default_rate": round(float(y_test.mean()), 6),
        },
    }
