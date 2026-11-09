"""Tests for editing and deleting transactions and deleting credit evaluations."""
import re
from datetime import date
from decimal import Decimal

import pytest

from app.auth.services import register_user
from app.extensions import db
from app.models import Category, Client, CreditApplication, Transaction
from app.services import repository
from app.transactions.forms import validate_transaction

PASSWORD = "a-long-password"
EDIT_FORM = {"type": "expense", "amount": "99.90", "date": "2026-11-07", "category": "Transport", "description": "Bus"}


@pytest.fixture(autouse=True)
def auth_on(app):
    app.config["AUTH_ENABLED"] = True


@pytest.fixture
def ana(app):
    return register_user("ana", "ana@example.com", PASSWORD)


@pytest.fixture
def luis(app):
    return register_user("luis", "luis@example.com", PASSWORD)


def client_for(app, user):
    client = app.test_client()
    client.post("/auth/login", data={"email": user.email, "password": PASSWORD})
    return client


@pytest.fixture
def ana_client(app, ana):
    return client_for(app, ana)


@pytest.fixture
def luis_client(app, luis):
    return client_for(app, luis)


def add_transaction(user, **overrides):
    data = {"type": "expense", "amount": Decimal("120500.00"), "date": date(2026, 11, 4),
            "category": "Food", "description": "Groceries", "user_id": user.id}
    return repository.save_transaction({**data, **overrides})


def add_evaluation(user, **overrides):
    data = {"age": 35, "monthly_income": 4000.0, "employment_status": "employed", "years_employment": 8.0,
            "credit_score": 760, "existing_debt": 2000.0, "dti_ratio": 15.0, "loan_amount": 10000.0,
            "loan_term": 36, "previous_loans": 2, "payment_history": "good", "risk_label": "Approved",
            "risk_percent": 3.3, "client_full_name": "Maria Lopez", "client_document": "100200300",
            "user_id": user.id}
    return repository.save_credit_application({**data, **overrides})


def stored(transaction_id):
    row = db.session.get(Transaction, transaction_id)
    return None if row is None else (row.type, row.amount, row.date, row.category.name, row.description)


def balance(client):
    html = client.get("/dashboard/").get_data(as_text=True)
    return re.search(r"Balance</h5>\s*<p[^>]*>([^<]+)</p>", html).group(1)


# Repository

def test_repository_returns_nothing_for_someone_elses_or_a_missing_transaction(ana, luis):
    mine = add_transaction(ana)
    assert repository.get_transaction(ana.id, mine["id"])["description"] == "Groceries"
    assert repository.get_transaction(luis.id, mine["id"]) is None
    assert repository.get_transaction(ana.id, 9999) is None


def test_repository_update_changes_fields_and_keeps_the_old_category(ana):
    mine = add_transaction(ana)
    values, _ = validate_transaction(EDIT_FORM)
    updated = repository.update_transaction(ana.id, mine["id"], values)
    assert (updated["category"], updated["amount"]) == ("Transport", Decimal("99.90"))
    assert stored(mine["id"]) == ("expense", Decimal("99.90"), date(2026, 11, 7), "Transport", "Bus")
    assert sorted(c.name for c in Category.query.all()) == ["Food", "Transport"]  # Food is now unused but kept


def test_repository_will_not_update_or_delete_someone_elses_records(ana, luis):
    mine = add_transaction(ana)
    evaluation = add_evaluation(ana)
    values, _ = validate_transaction(EDIT_FORM)
    assert repository.update_transaction(luis.id, mine["id"], values) is None
    assert repository.delete_transaction(luis.id, mine["id"]) is False
    assert repository.delete_credit_application(luis.id, evaluation["id"]) is False
    assert stored(mine["id"])[3] == "Food"
    assert CreditApplication.query.count() == 1


def test_repository_failed_update_rolls_back(ana):
    mine = add_transaction(ana)
    with pytest.raises(Exception):
        repository.update_transaction(ana.id, mine["id"], {**validate_transaction(EDIT_FORM)[0], "type": "gift"})
    assert stored(mine["id"])[3] == "Food"
    assert repository.list_transactions(ana.id)[0]["category"] == "Food"  # the session still works


def test_repository_delete_keeps_the_category_and_the_client(ana):
    transaction = add_transaction(ana)
    evaluation = add_evaluation(ana)
    assert repository.delete_transaction(ana.id, transaction["id"]) is True
    assert repository.delete_credit_application(ana.id, evaluation["id"]) is True
    assert Transaction.query.count() == 0 and CreditApplication.query.count() == 0
    assert Category.query.count() == 1
    assert Client.query.count() == 1
    assert repository.delete_transaction(ana.id, transaction["id"]) is False  # already gone


# Editing transactions

def test_edit_page_is_filled_with_the_transaction(ana, ana_client):
    mine = add_transaction(ana)
    html = ana_client.get(f"/transactions/{mine['id']}/edit").get_data(as_text=True)
    assert "Edit transaction" in html
    for value in ('value="120500.00"', 'value="2026-11-04"', 'value="Food"', 'value="Groceries"'):
        assert value in html
    assert f'action="/transactions/{mine["id"]}/edit"' in html


def test_edit_saves_the_changes(ana, ana_client):
    mine = add_transaction(ana)
    response = ana_client.post(f"/transactions/{mine['id']}/edit", data=EDIT_FORM)
    assert response.status_code == 302
    assert response.headers["Location"] == "/transactions/"
    assert stored(mine["id"]) == ("expense", Decimal("99.90"), date(2026, 11, 7), "Transport", "Bus")
    assert "Transaction updated." in ana_client.get("/transactions/").get_data(as_text=True)


@pytest.mark.parametrize(
    "field, value",
    [("type", "gift"), ("amount", "0"), ("amount", "1.234"), ("date", "07/11/2026"), ("category", ""),
     ("description", "x" * 256)],
)
def test_edit_validates_exactly_like_creation(ana, ana_client, field, value):
    mine = add_transaction(ana)
    bad = {**EDIT_FORM, field: value}
    _values, expected_errors = validate_transaction(bad)

    edit = ana_client.post(f"/transactions/{mine['id']}/edit", data=bad)
    create = ana_client.post("/transactions/new", data=bad)

    assert edit.status_code == create.status_code == 400
    for message in expected_errors:
        assert message in edit.get_data(as_text=True)
        assert message in create.get_data(as_text=True)
    assert stored(mine["id"])[3] == "Food"  # unchanged
    assert Transaction.query.count() == 1  # and nothing was created


# Deleting

def test_opening_the_delete_page_asks_and_deletes_nothing(ana, ana_client):
    mine = add_transaction(ana)
    html = ana_client.get(f"/transactions/{mine['id']}/delete").get_data(as_text=True)
    assert "This cannot be undone" in html
    assert "Groceries" in html and "120,500.00" in html
    assert re.search(rf'<form method="post" action="/transactions/{mine["id"]}/delete"', html)
    assert stored(mine["id"]) is not None


def test_delete_by_post_removes_the_transaction(ana, ana_client):
    mine = add_transaction(ana)
    response = ana_client.post(f"/transactions/{mine['id']}/delete")
    assert response.headers["Location"] == "/transactions/"
    assert stored(mine["id"]) is None
    assert Category.query.count() == 1  # the category stays
    assert "Transaction deleted." in ana_client.get("/transactions/").get_data(as_text=True)


def test_evaluations_can_be_deleted_from_the_history_but_not_edited(ana, ana_client):
    evaluation = add_evaluation(ana)
    history = ana_client.get("/credit/history").get_data(as_text=True)
    assert f'href="/credit/history/{evaluation["id"]}/delete"' in history
    assert "/edit" not in history  # evaluations have no edit action

    assert ana_client.get(f"/credit/history/{evaluation['id']}/edit").status_code == 404
    assert "This cannot be undone" in ana_client.get(f"/credit/history/{evaluation['id']}/delete").get_data(as_text=True)
    assert CreditApplication.query.count() == 1  # GET deletes nothing

    response = ana_client.post(f"/credit/history/{evaluation['id']}/delete")
    assert response.headers["Location"] == "/credit/history"
    assert CreditApplication.query.count() == 0
    assert Client.query.count() == 1
    assert "Evaluation deleted." in ana_client.get("/credit/history").get_data(as_text=True)


# Isolation between users: someone else's id behaves like a missing one (404, never 403)

def _foreign_requests(transaction_id, evaluation_id):
    return [
        ("get", f"/transactions/{transaction_id}/edit", None),
        ("post", f"/transactions/{transaction_id}/edit", EDIT_FORM),
        ("get", f"/transactions/{transaction_id}/delete", None),
        ("post", f"/transactions/{transaction_id}/delete", None),
        ("get", f"/credit/history/{evaluation_id}/delete", None),
        ("post", f"/credit/history/{evaluation_id}/delete", None),
    ]


def test_someone_elses_records_answer_404_and_stay_untouched(ana, luis_client):
    transaction = add_transaction(ana)
    evaluation = add_evaluation(ana)
    for method, path, data in _foreign_requests(transaction["id"], evaluation["id"]):
        response = getattr(luis_client, method)(path, data=data)
        assert response.status_code == 404, (method, path)
        assert "Page not found" in response.get_data(as_text=True)
    assert stored(transaction["id"]) == ("expense", Decimal("120500.00"), date(2026, 11, 4), "Food", "Groceries")
    assert CreditApplication.query.count() == 1


def test_missing_records_answer_the_same_404(ana, ana_client):
    for method, path, data in _foreign_requests(9999, 9999):
        assert getattr(ana_client, method)(path, data=data).status_code == 404, (method, path)


def test_a_user_only_sees_edit_and_delete_links_for_their_records(ana, luis, luis_client):
    add_transaction(ana)
    add_evaluation(ana)
    assert "/edit" not in luis_client.get("/transactions/").get_data(as_text=True)
    assert "/delete" not in luis_client.get("/credit/history").get_data(as_text=True)


def test_edit_and_delete_require_login(app, ana):
    mine = add_transaction(ana)
    anonymous = app.test_client()
    for path in (f"/transactions/{mine['id']}/edit", f"/transactions/{mine['id']}/delete"):
        assert anonymous.get(path).headers["Location"].startswith("/auth/login")
        assert anonymous.post(path).headers["Location"].startswith("/auth/login")
    assert stored(mine["id"]) is not None


# The dashboard follows edits and deletions

def test_dashboard_recalculates_after_edit_and_delete(ana, ana_client):
    base = {"date": "2026-11-01", "category": "Any", "description": ""}
    ana_client.post("/transactions/new", data={**base, "type": "income", "amount": "1000.00"})
    ana_client.post("/transactions/new", data={**base, "type": "expense", "amount": "250.00"})
    assert balance(ana_client) == "750.00"

    income, expense = sorted(repository.list_transactions(ana.id), key=lambda t: t["type"] != "income")
    ana_client.post(f"/transactions/{expense['id']}/edit", data={**base, "type": "expense", "amount": "400.00"})
    assert balance(ana_client) == "600.00"

    ana_client.post(f"/transactions/{expense['id']}/edit", data={**base, "type": "income", "amount": "400.00"})
    assert balance(ana_client) == "1,400.00"  # an expense turned into an income

    ana_client.post(f"/transactions/{income['id']}/delete")
    assert balance(ana_client) == "400.00"


def test_dashboard_evaluation_count_drops_after_a_deletion(ana, ana_client):
    first = add_evaluation(ana)
    add_evaluation(ana)
    ana_client.post(f"/credit/history/{first['id']}/delete")
    html = ana_client.get("/dashboard/").get_data(as_text=True)
    assert re.search(r"Credit evaluations</h5>\s*<p class=\"fs-3 fw-bold mb-0\">1</p>", html)


# CSRF protection on (it is off in TestingConfig for the other tests)

def _token(client, path):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


@pytest.fixture
def csrf_client(app, ana):
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    client.post("/auth/login", data={"email": ana.email, "password": PASSWORD, "csrf_token": _token(client, "/")})
    return client


def test_edit_without_csrf_token_is_rejected(ana, csrf_client):
    mine = add_transaction(ana)
    assert csrf_client.post(f"/transactions/{mine['id']}/edit", data=EDIT_FORM).status_code == 400
    assert stored(mine["id"])[3] == "Food"

    token = _token(csrf_client, f"/transactions/{mine['id']}/edit")
    assert csrf_client.post(f"/transactions/{mine['id']}/edit", data={**EDIT_FORM, "csrf_token": token}).status_code == 302
    assert stored(mine["id"])[3] == "Transport"


def test_delete_without_csrf_token_is_rejected(ana, csrf_client):
    mine = add_transaction(ana)
    evaluation = add_evaluation(ana)
    assert csrf_client.post(f"/transactions/{mine['id']}/delete").status_code == 400
    assert csrf_client.post(f"/credit/history/{evaluation['id']}/delete").status_code == 400
    assert stored(mine["id"]) is not None and CreditApplication.query.count() == 1

    token = _token(csrf_client, f"/transactions/{mine['id']}/delete")
    assert csrf_client.post(f"/transactions/{mine['id']}/delete", data={"csrf_token": token}).status_code == 302
    token = _token(csrf_client, f"/credit/history/{evaluation['id']}/delete")
    assert csrf_client.post(f"/credit/history/{evaluation['id']}/delete", data={"csrf_token": token}).status_code == 302
    assert stored(mine["id"]) is None and CreditApplication.query.count() == 0
