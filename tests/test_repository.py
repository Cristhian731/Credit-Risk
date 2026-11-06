"""Tests for the data access layer (app/services/repository.py).

They only use the public functions, so they must keep passing after
teammate A replaces the in-memory storage with database queries.
"""
from datetime import date
from decimal import Decimal

from app.services import repository


def _transaction(**overrides):
    data = {
        "type": "expense",
        "amount": Decimal("120500.00"),
        "date": date(2026, 11, 4),
        "category": "Food",
        "description": "Groceries",
        "user_id": 1,
    }
    return {**data, **overrides}


def _credit_application(**overrides):
    data = {
        "age": 35,
        "monthly_income": 4000.0,
        "employment_status": "employed",
        "years_employment": 8.0,
        "credit_score": 760,
        "existing_debt": 2000.0,
        "dti_ratio": 15.0,
        "loan_amount": 10000.0,
        "loan_term": 36,
        "previous_loans": 2,
        "payment_history": "good",
        "risk_label": "Approved",
        "risk_percent": 3.3,
        "client_id": None,
        "user_id": 1,
    }
    return {**data, **overrides}


def test_save_transaction_returns_record_with_id():
    saved = repository.save_transaction(_transaction())
    assert saved["id"] is not None
    assert saved["amount"] == Decimal("120500.00")
    assert saved["category"] == "Food"


def test_list_transactions_returns_saved_records_newest_first():
    older = repository.save_transaction(_transaction(date=date(2026, 11, 1)))
    newer = repository.save_transaction(_transaction(date=date(2026, 11, 5)))
    assert [t["id"] for t in repository.list_transactions(1)] == [newer["id"], older["id"]]


def test_list_transactions_only_returns_the_users_records():
    repository.save_transaction(_transaction(user_id=1))
    repository.save_transaction(_transaction(user_id=2, description="Someone else"))
    listed = repository.list_transactions(1)
    assert len(listed) == 1
    assert listed[0]["user_id"] == 1


def test_returned_records_cannot_change_stored_data():
    repository.save_transaction(_transaction())
    repository.list_transactions(1)[0]["amount"] = Decimal("0")
    assert repository.list_transactions(1)[0]["amount"] == Decimal("120500.00")


def test_save_and_list_credit_applications():
    first = repository.save_credit_application(_credit_application())
    second = repository.save_credit_application(_credit_application(risk_label="High Risk"))
    repository.save_credit_application(_credit_application(user_id=2))

    listed = repository.list_credit_applications(1)
    assert [a["id"] for a in listed] == [second["id"], first["id"]]
    assert listed[0]["risk_label"] == "High Risk"
    assert listed[1]["employment_status"] == "employed"


def test_nothing_is_listed_for_a_user_without_records():
    assert repository.list_transactions(99) == []
    assert repository.list_credit_applications(99) == []


def test_reset_with_seed_adds_demo_transactions():
    repository.reset(seed=True)
    assert len(repository.list_transactions(repository.DEMO_USER_ID)) == len(repository.DEMO_TRANSACTIONS)
