"""Tests for recording incomes and expenses."""
from datetime import date
from decimal import Decimal

import pytest

from app.services import repository
from app.transactions.forms import validate_transaction

# These tests run in demo mode (AUTH_ENABLED False), which needs the demo user.
pytestmark = pytest.mark.usefixtures("demo_user")

VALID_FORM = {
    "type": "expense",
    "amount": "45000.50",
    "date": "2026-11-06",
    "category": "Transport",
    "description": "Taxi",
}


def test_valid_form_is_typed():
    values, errors = validate_transaction(VALID_FORM)
    assert errors == []
    assert values == {
        "type": "expense",
        "amount": Decimal("45000.50"),
        "date": date(2026, 11, 6),
        "category": "Transport",
        "description": "Taxi",
    }


@pytest.mark.parametrize(
    "field, value",
    [("type", "gift"), ("amount", "0"), ("amount", "-5"), ("amount", "abc"), ("amount", "1.234"),
     ("date", "06/11/2026"), ("category", ""), ("description", "x" * 256)],
)
def test_invalid_value_is_rejected(field, value):
    values, errors = validate_transaction({**VALID_FORM, field: value})
    assert field not in values
    assert len(errors) == 1


def test_description_is_optional():
    values, errors = validate_transaction({**VALID_FORM, "description": ""})
    assert errors == []
    assert values["description"] == ""


def test_saving_a_transaction_stores_it_for_the_current_user(client, demo_user):
    response = client.post("/transactions/new", data=VALID_FORM)
    assert response.status_code == 302
    assert response.headers["Location"] == "/transactions/"

    (saved,) = repository.list_transactions(demo_user.id)
    assert saved["user_id"] == demo_user.id
    assert saved["amount"] == Decimal("45000.50")

    html = client.get("/transactions/").get_data(as_text=True)
    assert "Transaction saved." in html
    assert "Taxi" in html


def test_invalid_submission_keeps_form_data(client, demo_user):
    response = client.post("/transactions/new", data={**VALID_FORM, "amount": "-5"})
    html = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Amount must be a positive number" in html
    assert 'value="Transport"' in html
    assert repository.list_transactions(demo_user.id) == []


def test_dashboard_summarizes_saved_transactions(client):
    client.post("/transactions/new", data={**VALID_FORM, "type": "income", "amount": "1000"})
    client.post("/transactions/new", data={**VALID_FORM, "amount": "250"})
    html = client.get("/dashboard/").get_data(as_text=True)
    assert "1,000.00" in html
    assert "250.00" in html
    assert "750.00" in html
