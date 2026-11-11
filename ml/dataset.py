"""Load and split the Loan Default Prediction Dataset.

Owner: data (Sprint 1). See ml/data/README.md for the download and the
checksum, and docs/ML_PHASE.md for the contracts.
"""
import os

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

TEST_SIZE = 0.2
RANDOM_STATE = 42


def load(path=DEFAULT_DATA_PATH):
    """Read the dataset CSV and check its shape.

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
    raise NotImplementedError("Sprint 1 - owner: data")


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
    raise NotImplementedError("Sprint 1 - owner: data")
