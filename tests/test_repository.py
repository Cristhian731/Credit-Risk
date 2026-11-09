"""Tests for the data access layer (app/services/repository.py).

They only use the public functions and run against the real database.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.auth.services import register_user
from app.extensions import db
from app.models import Category, Client, CreditApplication, Transaction
from app.services import repository


@pytest.fixture
def user(app):
    return register_user("ana", "ana@example.com", "a-long-password")


@pytest.fixture
def other_user(app):
    return register_user("luis", "luis@example.com", "a-long-password")


def _transaction(user_id, **overrides):
    data = {
        "type": "expense",
        "amount": Decimal("120500.00"),
        "date": date(2026, 11, 4),
        "category": "Food",
        "description": "Groceries",
        "user_id": user_id,
    }
    return {**data, **overrides}


def _credit_application(user_id, **overrides):
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
        "client_full_name": "Maria Lopez",
        "client_document": "100200300",
        "user_id": user_id,
    }
    return {**data, **overrides}


def assert_no_orphan_rows():
    """SQLite does not enforce foreign keys by default; this checks them explicitly."""
    assert db.session.execute(text("PRAGMA foreign_key_check")).fetchall() == []


# Transactions

def test_save_transaction_returns_a_plain_record_with_id(user):
    saved = repository.save_transaction(_transaction(user.id))
    assert isinstance(saved, dict)
    assert saved["id"] is not None
    assert saved["amount"] == Decimal("120500.00")
    assert saved["category"] == "Food"
    assert saved["user_id"] == user.id


def test_saved_transaction_is_stored_in_the_database(user):
    repository.save_transaction(_transaction(user.id))
    row = Transaction.query.one()
    assert (row.type, row.amount, row.date, row.description) == ("expense", Decimal("120500.00"), date(2026, 11, 4), "Groceries")
    assert row.category.name == "Food"
    assert_no_orphan_rows()


def test_category_is_created_on_first_use_and_then_reused(user):
    assert Category.query.count() == 0
    repository.save_transaction(_transaction(user.id))
    repository.save_transaction(_transaction(user.id, description="More food"))
    repository.save_transaction(_transaction(user.id, category="  food "))  # same name, other spelling
    assert Category.query.count() == 1


def test_same_name_as_income_and_expense_makes_two_categories(user):
    repository.save_transaction(_transaction(user.id, type="expense", category="Other"))
    repository.save_transaction(_transaction(user.id, type="income", category="Other"))
    assert sorted(c.type for c in Category.query.all()) == ["expense", "income"]


def test_each_user_has_their_own_categories(user, other_user):
    repository.save_transaction(_transaction(user.id))
    repository.save_transaction(_transaction(other_user.id))
    assert sorted(c.user_id for c in Category.query.all()) == sorted([user.id, other_user.id])


def test_list_transactions_returns_saved_records_newest_first(user):
    older = repository.save_transaction(_transaction(user.id, date=date(2026, 11, 1)))
    newer = repository.save_transaction(_transaction(user.id, date=date(2026, 11, 5)))
    same_day = repository.save_transaction(_transaction(user.id, date=date(2026, 11, 5)))
    assert [t["id"] for t in repository.list_transactions(user.id)] == [same_day["id"], newer["id"], older["id"]]


def test_list_transactions_only_returns_the_users_records(user, other_user):
    repository.save_transaction(_transaction(user.id))
    repository.save_transaction(_transaction(other_user.id, description="Someone else"))
    listed = repository.list_transactions(user.id)
    assert len(listed) == 1
    assert listed[0]["user_id"] == user.id


def test_returned_records_cannot_change_stored_data(user):
    repository.save_transaction(_transaction(user.id))
    repository.list_transactions(user.id)[0]["amount"] = Decimal("0")
    assert repository.list_transactions(user.id)[0]["amount"] == Decimal("120500.00")


def test_failed_save_rolls_back_and_the_session_keeps_working(user):
    with pytest.raises(Exception):
        repository.save_transaction(_transaction(user.id, type="gift"))
    assert Transaction.query.count() == 0
    assert Category.query.count() == 0
    repository.save_transaction(_transaction(user.id))
    assert Transaction.query.count() == 1


# Credit applications and clients

def test_save_credit_application_creates_the_client(user):
    saved = repository.save_credit_application(_credit_application(user.id))
    assert saved["id"] is not None
    assert saved["client_id"] is not None
    assert (saved["client_full_name"], saved["client_document"]) == ("Maria Lopez", "100200300")
    assert Client.query.one().user_id == user.id
    assert_no_orphan_rows()


def test_client_is_found_by_document_within_the_user(user):
    first = repository.save_credit_application(_credit_application(user.id))
    second = repository.save_credit_application(_credit_application(user.id, risk_label="High Risk"))
    assert first["client_id"] == second["client_id"]
    assert Client.query.count() == 1
    assert CreditApplication.query.count() == 2


def test_client_lookup_ignores_case_and_extra_spaces_in_the_document(user):
    repository.save_credit_application(_credit_application(user.id, client_document="AB 123"))
    repository.save_credit_application(_credit_application(user.id, client_document="ab   123"))
    assert Client.query.count() == 1


def test_the_latest_spelling_of_the_client_name_is_kept(user):
    repository.save_credit_application(_credit_application(user.id, client_full_name="Maria Lopes"))
    repository.save_credit_application(_credit_application(user.id, client_full_name="Maria Lopez"))
    assert Client.query.one().full_name == "Maria Lopez"


def test_same_document_for_two_users_makes_two_clients(user, other_user):
    repository.save_credit_application(_credit_application(user.id))
    repository.save_credit_application(_credit_application(other_user.id))
    assert Client.query.count() == 2


def test_save_and_list_credit_applications(user, other_user):
    first = repository.save_credit_application(_credit_application(user.id))
    second = repository.save_credit_application(_credit_application(user.id, risk_label="High Risk"))
    repository.save_credit_application(_credit_application(other_user.id))

    listed = repository.list_credit_applications(user.id)
    assert [a["id"] for a in listed] == [second["id"], first["id"]]
    assert listed[0]["risk_label"] == "High Risk"
    assert listed[1]["employment_status"] == "employed"
    assert listed[0]["client_full_name"] == "Maria Lopez"
    assert listed[0]["created_at"] is not None


def test_list_credit_applications_can_be_limited(user):
    for _ in range(3):
        repository.save_credit_application(_credit_application(user.id))
    assert len(repository.list_credit_applications(user.id, limit=2)) == 2


def test_count_credit_applications_counts_only_the_users_records(user, other_user):
    repository.save_credit_application(_credit_application(user.id))
    repository.save_credit_application(_credit_application(user.id))
    repository.save_credit_application(_credit_application(other_user.id))
    assert repository.count_credit_applications(user.id) == 2
    assert repository.count_credit_applications(other_user.id) == 1


def test_failed_credit_save_does_not_leave_a_client_behind(user):
    with pytest.raises(Exception):
        repository.save_credit_application(_credit_application(user.id, risk_label="Bogus"))
    assert Client.query.count() == 0
    assert CreditApplication.query.count() == 0


def test_nothing_is_listed_for_a_user_without_records(app):
    assert repository.list_transactions(99) == []
    assert repository.list_credit_applications(99) == []
    assert repository.count_credit_applications(99) == 0
