"""Tests for the ML phase feature sets in ml/features.py."""
import pytest

from app.credit.forms import validate_form
from ml.features import (
    CATEGORICAL_ENCODINGS,
    CLIP_RANGES,
    DEFAULT_FEATURE_SET,
    EMPLOYMENT_TYPE_MAP,
    FEATURE_ORDER,
    FEATURE_SETS,
    PLACEHOLDER_FEATURE_SET,
    to_model_frame,
)


FORM = {
    "age": "35",
    "monthly_income": "4000",
    "employment_status": "self_employed",
    "years_employment": "2.5",
    "credit_score": "850",
    "existing_debt": "2000",
    "dti_ratio": "15",
    "loan_amount": "10000",
    "loan_term": "120",
    "previous_loans": "0",
    "payment_history": "good",
}


# Contract (passes now)

def test_feature_order_of_the_form_is_unchanged():
    assert FEATURE_ORDER == [
        "age", "monthly_income", "employment_status", "years_employment", "credit_score",
        "existing_debt", "dti_ratio", "loan_amount", "loan_term", "previous_loans", "payment_history",
    ]


def test_v2_feature_set_uses_nine_dataset_columns():
    v2 = FEATURE_SETS[DEFAULT_FEATURE_SET]
    assert DEFAULT_FEATURE_SET == "v2-loan-default"
    assert len(v2["columns"]) == 9
    assert set(v2["categorical"]) <= set(v2["columns"])
    assert "InterestRate" not in v2["columns"]


def test_placeholder_feature_set_is_the_form_order():
    assert list(FEATURE_SETS[PLACEHOLDER_FEATURE_SET]["columns"]) == FEATURE_ORDER


def test_every_employment_status_has_a_dataset_category():
    assert set(EMPLOYMENT_TYPE_MAP) == set(CATEGORICAL_ENCODINGS["employment_status"])
    assert set(EMPLOYMENT_TYPE_MAP.values()) <= {"Full-time", "Part-time", "Self-employed", "Unemployed"}


def test_clip_ranges_match_the_dataset():
    assert CLIP_RANGES == {
        "Age": (18, 69),
        "LoanTerm": (12, 60),
        "NumCreditLines": (1, 4),
        "CreditScore": (300, 849),
    }


# Behaviour

def _frame(**overrides):
    values, errors = validate_form({**FORM, **overrides})
    assert errors == []
    return to_model_frame(values)


def test_to_model_frame_returns_one_row_in_feature_set_order():
    """The frame has one row and exactly the v2 columns, in order."""
    frame = _frame()
    assert len(frame) == 1
    assert tuple(frame.columns) == FEATURE_SETS[DEFAULT_FEATURE_SET]["columns"]


def test_to_model_frame_converts_units():
    """years_employment 2.5 -> MonthsEmployed 30; dti_ratio 15 -> DTIRatio 0.15."""
    row = _frame().iloc[0]
    assert row["MonthsEmployed"] == 30
    assert row["DTIRatio"] == pytest.approx(0.15)
    assert row["LoanAmount"] == 10000


@pytest.mark.parametrize("status, category", sorted(EMPLOYMENT_TYPE_MAP.items()))
def test_to_model_frame_maps_employment_status(status, category):
    """Each form employment status becomes its dataset EmploymentType."""
    assert _frame(employment_status=status).iloc[0]["EmploymentType"] == category


def test_to_model_frame_clips_to_dataset_ranges():
    """credit_score 850 -> 849, loan_term 120 -> 60, previous_loans 0 -> 1, age 90 -> 69."""
    row = _frame(age="90").iloc[0]
    assert row["CreditScore"] == 849
    assert row["LoanTerm"] == 60
    assert row["NumCreditLines"] == 1
    assert row["Age"] == 69


def test_to_model_frame_ignores_debt_and_payment_history():
    """Changing existing_debt or payment_history does not change the frame."""
    assert _frame().equals(_frame(existing_debt="90000", payment_history="poor"))


def test_to_model_frame_rejects_an_unknown_feature_set():
    """An unknown feature_set raises ValueError."""
    values, _errors = validate_form(FORM)
    with pytest.raises(ValueError):
        to_model_frame(values, "v9-unknown")
