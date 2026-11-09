"""Tests that data really lives in the database and that nothing calculable is stored."""
import re
from datetime import date
from decimal import Decimal

import pytest
from flask_migrate import upgrade
from sqlalchemy import text

from app import create_app
from app.auth.services import register_user
from app.extensions import db
from app.services import repository
from config import TestingConfig

FORBIDDEN_COLUMN_WORDS = ("total", "balance", "net_worth", "networth", "savings", "equity")


@pytest.fixture
def database_file(tmp_path, monkeypatch):
    """Point the testing config to a migrated SQLite file, so apps can be 'restarted' on it."""
    path = tmp_path / "persist.db"
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{path}")
    first = create_app("testing")
    with first.app_context():
        upgrade()
        db.session.remove()
        db.engine.dispose()
    return path


def restart():
    """A brand new application process on the same database file."""
    return create_app("testing")


def test_data_survives_an_application_restart(database_file):
    before = restart()
    with before.app_context():
        user = register_user("ana", "ana@example.com", "a-long-password")
        repository.save_transaction(
            {"type": "income", "amount": Decimal("1500.50"), "date": date(2026, 11, 1),
             "category": "Salary", "description": "Pay", "user_id": user.id}
        )
        repository.save_credit_application(
            {"age": 35, "monthly_income": 4000.0, "employment_status": "employed", "years_employment": 8.0,
             "credit_score": 760, "existing_debt": 2000.0, "dti_ratio": 15.0, "loan_amount": 10000.0,
             "loan_term": 36, "previous_loans": 2, "payment_history": "good", "risk_label": "Approved",
             "risk_percent": 3.3, "client_full_name": "Maria Lopez", "client_document": "100200300",
             "user_id": user.id}
        )
        user_id = user.id
        db.session.remove()
        db.engine.dispose()

    after = restart()
    with after.app_context():
        (transaction,) = repository.list_transactions(user_id)
        assert (transaction["category"], transaction["amount"], transaction["date"]) == ("Salary", Decimal("1500.50"), date(2026, 11, 1))
        (application,) = repository.list_credit_applications(user_id)
        assert (application["client_full_name"], application["risk_label"]) == ("Maria Lopez", "Approved")
        assert db.session.execute(text("PRAGMA foreign_key_check")).fetchall() == []
        db.session.remove()
        db.engine.dispose()


def test_the_login_survives_a_restart_with_the_same_account(database_file):
    first = restart()
    with first.app_context():
        register_user("ana", "ana@example.com", "a-long-password")
        db.session.remove()
        db.engine.dispose()

    second = restart()
    second.config["AUTH_ENABLED"] = True
    response = second.test_client().post("/auth/login", data={"email": "ana@example.com", "password": "a-long-password"})
    assert response.headers["Location"] == "/dashboard/"
    with second.app_context():
        db.session.remove()
        db.engine.dispose()


def test_no_table_stores_a_calculable_value(app):
    """Totals, balances and net worth are computed when read, never stored."""
    for table in db.metadata.tables.values():
        for column in table.columns:
            assert not any(word in column.name.lower() for word in FORBIDDEN_COLUMN_WORDS), f"{table.name}.{column.name}"


def test_dashboard_totals_follow_the_transactions_without_being_stored(client, app):
    app.config["AUTH_ENABLED"] = True
    register_user("ana", "ana@example.com", "a-long-password")
    client.post("/auth/login", data={"email": "ana@example.com", "password": "a-long-password"})

    def dashboard():
        return client.get("/dashboard/").get_data(as_text=True)

    base = {"date": "2026-11-01", "category": "Any", "description": ""}
    client.post("/transactions/new", data={**base, "type": "income", "amount": "1000.00"})
    client.post("/transactions/new", data={**base, "type": "expense", "amount": "250.00"})
    assert "750.00" in dashboard()

    client.post("/transactions/new", data={**base, "type": "expense", "amount": "100.00"})
    html = dashboard()
    assert "650.00" in html  # recalculated on the next read
    assert not re.search(r"750\.00", html.split("Balance")[1].split("</p>")[0])


def test_each_user_only_sees_and_sums_their_own_transactions(client, app):
    app.config["AUTH_ENABLED"] = True
    for name in ("ana", "luis"):
        register_user(name, f"{name}@example.com", "a-long-password")
    form = {"date": "2026-11-01", "category": "Any", "description": "", "type": "income"}

    client.post("/auth/login", data={"email": "ana@example.com", "password": "a-long-password"})
    client.post("/transactions/new", data={**form, "amount": "999.00"})
    client.post("/auth/logout")

    client.post("/auth/login", data={"email": "luis@example.com", "password": "a-long-password"})
    assert "999.00" not in client.get("/dashboard/").get_data(as_text=True)
    assert "999.00" not in client.get("/transactions/").get_data(as_text=True)
