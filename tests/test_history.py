"""Tests for the customer fields and the evaluation history (AUTH_ENABLED True)."""
import re

import pytest

from app.auth.services import register_user
from app.credit.forms import validate_client
from app.models import Client, CreditApplication

CREDIT_FORM = {
    "client_full_name": "Maria Lopez",
    "client_document": "100200300",
    "age": "35",
    "monthly_income": "4000",
    "employment_status": "employed",
    "years_employment": "8",
    "credit_score": "760",
    "existing_debt": "2000",
    "dti_ratio": "15",
    "loan_amount": "10000",
    "loan_term": "36",
    "previous_loans": "2",
    "payment_history": "good",
}


@pytest.fixture(autouse=True)
def auth_on(app):
    app.config["AUTH_ENABLED"] = True


def login_as(client, name):
    register_user(name, f"{name}@example.com", "a-long-password")
    client.post("/auth/login", data={"email": f"{name}@example.com", "password": "a-long-password"})
    return client


@pytest.fixture
def logged_in(client):
    return login_as(client, "ana")


# Customer fields

def test_credit_form_asks_for_the_customer(logged_in):
    html = logged_in.get("/credit/").get_data(as_text=True)
    for name in ("client_full_name", "client_document"):
        assert f'name="{name}"' in html


def test_valid_customer_fields_are_cleaned():
    clean, errors = validate_client({"client_full_name": "  Maria   Lopez ", "client_document": " 100 200 "})
    assert errors == []
    assert clean == {"client_full_name": "Maria Lopez", "client_document": "100 200"}


@pytest.mark.parametrize(
    "field, value",
    [("client_full_name", ""), ("client_full_name", "M"), ("client_full_name", "x" * 121),
     ("client_document", ""), ("client_document", "12"), ("client_document", "1" * 31),
     ("client_document", "12<script>"), ("client_document", "-1234"), ("client_document", "1234;")],
)
def test_invalid_customer_field_is_rejected(field, value):
    clean, errors = validate_client({"client_full_name": "Maria Lopez", "client_document": "100200300", field: value})
    assert field not in clean
    assert len(errors) == 1


@pytest.mark.parametrize("field", ["client_full_name", "client_document"])
def test_submission_without_customer_data_is_rejected_and_not_saved(logged_in, field):
    response = logged_in.post("/credit/", data={**CREDIT_FORM, field: ""})
    html = response.get_data(as_text=True)
    assert response.status_code == 400
    assert 'value="100200300"' in html or field == "client_document"  # the rest of the form is kept
    assert CreditApplication.query.count() == 0
    assert Client.query.count() == 0


# History

def test_history_is_empty_at_first(logged_in):
    html = logged_in.get("/credit/history").get_data(as_text=True)
    assert "No evaluations yet." in html


def test_history_lists_the_evaluations_newest_first(logged_in):
    logged_in.post("/credit/", data=CREDIT_FORM)
    logged_in.post("/credit/", data={**CREDIT_FORM, "client_full_name": "Pedro Gomez", "client_document": "55.66.77"})
    html = logged_in.get("/credit/history").get_data(as_text=True)
    assert "Maria Lopez" in html and "Pedro Gomez" in html
    assert "100200300" in html and "55.66.77" in html
    assert html.index("Pedro Gomez") < html.index("Maria Lopez")  # newest first
    assert re.search(r"Approved|Medium Risk|High Risk", html)


def test_history_only_shows_the_users_own_evaluations(client):
    login_as(client, "ana")
    client.post("/credit/", data=CREDIT_FORM)
    client.post("/auth/logout")
    login_as(client, "luis")
    html = client.get("/credit/history").get_data(as_text=True)
    assert "Maria Lopez" not in html
    assert "No evaluations yet." in html


def test_history_requires_login(client):
    response = client.get("/credit/history")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/login")


def test_evaluating_the_same_customer_twice_keeps_one_client(logged_in):
    logged_in.post("/credit/", data=CREDIT_FORM)
    logged_in.post("/credit/", data=CREDIT_FORM)
    assert Client.query.count() == 1
    assert CreditApplication.query.count() == 2


def test_history_is_linked_from_the_credit_pages_without_a_new_menu_entry(logged_in):
    form_page = logged_in.get("/credit/").get_data(as_text=True)
    assert 'href="/credit/history"' in form_page
    logged_in.post("/credit/", data=CREDIT_FORM)
    assert 'href="/credit/history"' in logged_in.get("/credit/result").get_data(as_text=True)

    nav = re.search(r"<nav.*?</nav>", form_page, re.DOTALL).group(0)
    assert "history" not in nav.lower()
    labels = re.findall(r'class="nav-link[^"]*"[^>]*>([^<]+)<', nav)
    assert [label.strip() for label in labels] == ["Transactions", "Dashboard", "Credit Evaluation"]


def test_dashboard_counts_the_users_evaluations(logged_in):
    logged_in.post("/credit/", data=CREDIT_FORM)
    logged_in.post("/credit/", data=CREDIT_FORM)
    html = logged_in.get("/dashboard/").get_data(as_text=True)
    assert re.search(r"Credit evaluations</h5>\s*<p class=\"fs-3 fw-bold mb-0\">2</p>", html)
