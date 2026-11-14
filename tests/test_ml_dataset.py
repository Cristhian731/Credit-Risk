"""Tests for ml/dataset.py and the synthetic sample fixture."""
import csv
import os

import pytest

from ml import dataset

SAMPLE = os.path.join(os.path.dirname(__file__), "fixtures", "loan_default_sample.csv")


def _sample_rows():
    with open(SAMPLE, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return reader.fieldnames, list(reader)


# The fixture itself (passes now)

def test_sample_has_the_18_dataset_columns_in_order():
    header, _rows = _sample_rows()
    assert tuple(header) == dataset.RAW_COLUMNS
    assert len(dataset.RAW_COLUMNS) == 18


def test_sample_has_60_rows_with_about_15_percent_defaults():
    _header, rows = _sample_rows()
    defaults = [row for row in rows if row["Default"] == "1"]
    assert len(rows) == 60
    assert {row["Default"] for row in rows} == {"0", "1"}
    assert 0.10 <= len(defaults) / len(rows) <= 0.20


def test_sample_ids_are_unique_and_marked_synthetic():
    _header, rows = _sample_rows()
    ids = [row["LoanID"] for row in rows]
    assert len(set(ids)) == len(ids)
    assert all(loan_id.startswith("SYN") for loan_id in ids)


def test_sample_covers_every_employment_type():
    _header, rows = _sample_rows()
    assert {row["EmploymentType"] for row in rows} == {"Full-time", "Part-time", "Self-employed", "Unemployed"}


# Behaviour

def test_load_returns_the_18_columns_with_an_integer_target():
    """load(SAMPLE) returns 60 rows, columns == RAW_COLUMNS and Default as int 0/1."""
    df = dataset.load(SAMPLE)
    assert tuple(df.columns) == dataset.RAW_COLUMNS
    assert len(df) == 60
    assert set(df[dataset.TARGET_COLUMN].unique()) == {0, 1}


def test_load_rejects_a_file_with_a_missing_column(tmp_path):
    """A CSV without the Default column raises ValueError naming the column."""
    path = tmp_path / "broken.csv"
    with open(SAMPLE, encoding="utf-8") as fh:
        lines = [line.rsplit(",", 1)[0] for line in fh.read().splitlines()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Default"):
        dataset.load(str(path))


def test_load_reports_a_missing_file():
    """A path that does not exist raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        dataset.load("does-not-exist.csv")


def test_split_is_stratified_80_20_and_drops_id_and_target():
    """split() keeps 20 % for test, the default rate in both parts and no LoanID/Default columns."""
    df = dataset.load(SAMPLE)
    X_train, X_test, y_train, y_test = dataset.split(df)
    assert len(X_test) == 12 and len(X_train) == 48
    assert dataset.ID_COLUMN not in X_train.columns
    assert dataset.TARGET_COLUMN not in X_train.columns
    assert abs(y_train.mean() - y_test.mean()) < 0.05


def test_split_is_reproducible():
    """Two calls on the same frame return the same test index (seed 42)."""
    df = dataset.load(SAMPLE)
    assert list(dataset.split(df)[1].index) == list(dataset.split(df)[1].index)
