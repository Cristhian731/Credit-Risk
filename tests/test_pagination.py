"""Tests for server-side pagination (20 per page) of transactions and the history."""
import re
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.auth.services import register_user
from app.extensions import db
from app.services import repository

PASSWORD = "a-long-password"
PAGE_SIZE = 20


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


def add_transactions(user, count, kind="expense", amount="10.00"):
    start = date(2026, 1, 1)
    for number in range(count):
        repository.save_transaction({
            "type": kind, "amount": Decimal(amount), "date": start + timedelta(days=number),
            "category": "Any", "description": f"{user.username}-{number:03d}", "user_id": user.id,
        })


def add_evaluations(user, count):
    for number in range(count):
        repository.save_credit_application({
            "age": 35, "monthly_income": 4000.0, "employment_status": "employed", "years_employment": 8.0,
            "credit_score": 760, "existing_debt": 2000.0, "dti_ratio": 15.0, "loan_amount": 10000.0,
            "loan_term": 36, "previous_loans": 2, "payment_history": "good", "risk_label": "Approved",
            "risk_percent": 3.3, "client_full_name": f"Client {number:03d}", "client_document": f"DOC{number:03d}",
            "user_id": user.id,
        })


def descriptions(html, prefix):
    return re.findall(rf"<td>({prefix}-\d{{3}})</td>", html)


# Repository

def test_pages_split_the_records_in_the_same_order_as_the_full_list(ana):
    add_transactions(ana, 45)
    pages = [repository.paginate_transactions(ana.id, number, PAGE_SIZE) for number in (1, 2, 3)]
    assert [len(p["items"]) for p in pages] == [20, 20, 5]
    assert all((p["pages"], p["total"]) == (3, 45) for p in pages)
    assert [t["id"] for p in pages for t in p["items"]] == [t["id"] for t in repository.list_transactions(ana.id)]


def test_page_boundaries(ana):
    add_transactions(ana, 40)  # exactly two full pages
    assert repository.paginate_transactions(ana.id, 2, PAGE_SIZE)["pages"] == 2
    assert len(repository.paginate_transactions(ana.id, 2, PAGE_SIZE)["items"]) == 20
    add_transactions(ana, 1)
    assert repository.paginate_transactions(ana.id, 3, PAGE_SIZE)["pages"] == 3


@pytest.mark.parametrize("page, expected", [(0, 1), (-5, 1), (None, 1), ("2", 1), (True, 1), (2, 2), (3, 3), (4, 3), (999, 3)])
def test_invalid_or_out_of_range_pages_are_clamped(ana, page, expected):
    add_transactions(ana, 45)
    assert repository.paginate_transactions(ana.id, page, PAGE_SIZE)["page"] == expected


def test_an_empty_list_has_one_empty_page(ana):
    page = repository.paginate_transactions(ana.id, 5, PAGE_SIZE)
    assert (page["items"], page["page"], page["pages"], page["total"]) == ([], 1, 1, 0)


def test_the_database_cuts_the_page(app, ana):
    """LIMIT/OFFSET go to the SQL query: rows outside the page are never loaded."""
    add_transactions(ana, 45)
    statements = []

    def capture(_conn, _cursor, statement, parameters, _context, _many):
        statements.append((statement, parameters))

    event.listen(db.engine, "before_cursor_execute", capture)
    try:
        repository.paginate_transactions(ana.id, 2, PAGE_SIZE)
    finally:
        event.remove(db.engine, "before_cursor_execute", capture)

    page_queries = [s for s, _ in statements if "FROM transactions" in s and "count(" not in s.lower()]
    assert page_queries and all("LIMIT" in s and "OFFSET" in s for s in page_queries)


# Pages through HTTP

def test_transactions_page_two_shows_the_next_twenty(app, ana):
    add_transactions(ana, 45)
    client = client_for(app, ana)
    first = descriptions(client.get("/transactions/").get_data(as_text=True), "ana")
    second = descriptions(client.get("/transactions/?page=2").get_data(as_text=True), "ana")
    third = descriptions(client.get("/transactions/?page=3").get_data(as_text=True), "ana")
    assert (len(first), len(second), len(third)) == (20, 20, 5)
    assert first[0] == "ana-044" and second[0] == "ana-024" and third[-1] == "ana-000"  # newest date first


@pytest.mark.parametrize("query, expected_page", [("page=0", 1), ("page=-1", 1), ("page=abc", 1), ("page=", 1),
                                                  ("page=1.5", 1), ("page=999", 3), ("page=99999999999999999999", 3)])
def test_bad_page_parameters_never_fail(app, ana, query, expected_page):
    add_transactions(ana, 45)
    response = client_for(app, ana).get(f"/transactions/?{query}")
    assert response.status_code == 200
    assert f"Page {expected_page} of 3" in response.get_data(as_text=True)


def test_previous_and_next_links(app, ana):
    add_transactions(ana, 45)
    client = client_for(app, ana)
    first = client.get("/transactions/").get_data(as_text=True)
    assert 'href="/transactions/?page=2"' in first and "?page=0" not in first
    middle = client.get("/transactions/?page=2").get_data(as_text=True)
    assert 'href="/transactions/?page=1"' in middle and 'href="/transactions/?page=3"' in middle
    last = client.get("/transactions/?page=3").get_data(as_text=True)
    assert 'href="/transactions/?page=2"' in last and "?page=4" not in last


def test_no_pager_when_everything_fits_in_one_page(app, ana):
    add_transactions(ana, 20)
    html = client_for(app, ana).get("/transactions/").get_data(as_text=True)
    assert "Page 1 of" not in html and "?page=" not in html


def test_history_is_paginated_newest_first(app, ana):
    add_evaluations(ana, 25)
    client = client_for(app, ana)
    first = client.get("/credit/history").get_data(as_text=True)
    second = client.get("/credit/history?page=2").get_data(as_text=True)
    assert len(re.findall(r"<td>Client \d{3}</td>", first)) == 20
    assert re.findall(r"<td>(Client \d{3})</td>", second) == [f"Client {n:03d}" for n in range(4, -1, -1)]
    assert "Page 2 of 2" in second
    assert client.get("/credit/history?page=abc").status_code == 200


# Isolation and dashboard

def test_each_user_pages_only_through_their_own_records(app, ana, luis):
    add_transactions(ana, 45)
    add_transactions(luis, 3)
    luis_page = repository.paginate_transactions(luis.id, 1, PAGE_SIZE)
    assert (luis_page["total"], luis_page["pages"]) == (3, 1)

    client = client_for(app, luis)
    for query in ("", "?page=2", "?page=3"):
        html = client.get(f"/transactions/{query}").get_data(as_text=True)
        assert descriptions(html, "ana") == []
        assert len(descriptions(html, "luis")) == 3


def test_dashboard_totals_cover_every_transaction_not_one_page(app, ana):
    add_transactions(ana, 45, kind="expense", amount="10.00")
    add_transactions(ana, 1, kind="income", amount="1000.00")
    totals = repository.transaction_totals(ana.id)
    assert totals == {"income": Decimal("1000.00"), "expense": Decimal("450.00"), "balance": Decimal("550.00")}
    html = client_for(app, ana).get("/dashboard/").get_data(as_text=True)
    assert "450.00" in html and "550.00" in html


def test_dashboard_totals_without_transactions_are_zero(ana):
    assert repository.transaction_totals(ana.id) == {"income": Decimal("0.00"), "expense": Decimal("0.00"), "balance": Decimal("0.00")}
