"""Tests for flask seed-demo and the persisted demo user."""
import pytest

from app.auth.services import DEMO_EMAIL, DEMO_USERNAME, register_user
from app.models import Category, Transaction, User
from app.seed import SAMPLE_LABEL, demo_transactions
from app.services import repository


def run_seed(app):
    return app.test_cli_runner().invoke(args=["seed-demo"])


def test_nothing_is_created_without_running_seed_demo(app):
    assert User.query.count() == 0
    assert Transaction.query.count() == 0


def test_seed_demo_creates_the_demo_user_and_sample_transactions(app):
    result = run_seed(app)
    assert result.exit_code == 0, result.output
    assert "Demo user created." in result.output
    assert f"Sample transactions added: {len(demo_transactions())}" in result.output

    demo = User.query.filter_by(email=DEMO_EMAIL).one()
    assert demo.username == DEMO_USERNAME
    assert len(repository.list_transactions(demo.id)) == len(demo_transactions())
    assert {c.name for c in Category.query.all()} == {"Salary", "Housing", "Food", "Loan payment"}


def test_seed_demo_can_run_again_without_duplicating_anything(app):
    run_seed(app)
    result = run_seed(app)
    assert result.exit_code == 0, result.output
    assert "Demo user already exists." in result.output
    assert "Sample transactions added: 0" in result.output
    assert User.query.count() == 1
    assert Transaction.query.count() == len(demo_transactions())


def test_seed_demo_does_not_touch_real_users(app):
    real = register_user("ana", "ana@example.com", "a-long-password")
    run_seed(app)
    assert repository.list_transactions(real.id) == []
    assert User.query.count() == 2


def test_only_the_configured_demo_password_logs_in_as_the_demo_user(app, client):
    run_seed(app)
    app.config["AUTH_ENABLED"] = True
    for password in ("", "demo", "password", DEMO_USERNAME, "a-long-password"):
        client.post("/auth/login", data={"email": DEMO_EMAIL, "password": password})
        with client.session_transaction() as client_session:
            assert "user_id" not in client_session
    client.post("/auth/login", data={"email": DEMO_EMAIL, "password": app.config["DEMO_PASSWORD"]})
    with client.session_transaction() as client_session:
        assert "user_id" in client_session


def test_the_demo_email_cannot_be_registered(app):
    with pytest.raises(ValueError):
        register_user("somebody", DEMO_EMAIL, "a-long-password")
    run_seed(app)
    with pytest.raises(ValueError):
        register_user("somebody", DEMO_EMAIL.upper(), "a-long-password")


def test_demo_mode_shows_the_seeded_data_and_only_that(app, client):
    run_seed(app)
    real = register_user("ana", "ana@example.com", "a-long-password")
    repository.save_transaction(
        {"type": "income", "amount": 1, "date": demo_transactions()[0]["date"], "category": "Mine", "description": "", "user_id": real.id}
    )
    html = client.get("/transactions/").get_data(as_text=True)
    assert "Sample data: Monthly salary" in html
    assert "Mine" not in html  # the first real user does not share the demo user's data


def test_sample_data_is_labeled_and_fills_the_credit_form(app):
    run_seed(app)
    demo = User.query.filter_by(email=DEMO_EMAIL).one()
    rows = repository.list_transactions(demo.id)
    assert rows and all(SAMPLE_LABEL in row["description"] for row in rows)
    summary = repository.finance_summary_for_credit(demo.id)
    assert len(summary["months"]) == 3
    assert str(summary["monthly_income"]) == "4200.00"
    assert str(summary["debt_monthly"]) == "600.00"
    assert round(float(summary["dti_percent"]), 1) == 14.3


def test_sample_data_is_not_added_when_the_demo_account_has_transactions(app):
    run_seed(app)
    first = Transaction.query.count()
    run_seed(app)
    assert Transaction.query.count() == first


def test_sample_finances_are_added_when_only_older_transactions_exist(app):
    from datetime import date
    from app.seed import ensure_demo_user

    demo, _ = ensure_demo_user("x" * 12)
    repository.save_transaction(
        {"type": "income", "amount": 1, "date": date(2024, 1, 5), "category": "Old", "description": "old", "user_id": demo.id}
    )
    result = run_seed(app)
    assert result.exit_code == 0, result.output
    assert f"Sample transactions added: {len(demo_transactions())}" in result.output
    summary = repository.finance_summary_for_credit(demo.id)
    assert str(summary["monthly_income"]) == "4200.00"
    assert round(float(summary["dti_percent"]), 1) == 14.3
    again = run_seed(app)
    assert "Sample transactions added: 0" in again.output
    assert Transaction.query.count() == len(demo_transactions()) + 1


def test_credit_form_of_the_demo_account_is_prefilled_after_the_seed(app, client):
    run_seed(app)
    html = client.get("/credit/?source=finance").get_data(as_text=True)
    assert 'value="4200.00"' in html
    assert 'value="14.3"' in html
