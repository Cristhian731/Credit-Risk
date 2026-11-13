"""Tests for flask seed-demo and the persisted demo user."""
import pytest

from app.auth.services import DEMO_EMAIL, DEMO_USERNAME, register_user
from app.models import Category, Transaction, User
from app.seed import DEMO_TRANSACTIONS
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
    assert f"Sample transactions added: {len(DEMO_TRANSACTIONS)}" in result.output

    demo = User.query.filter_by(email=DEMO_EMAIL).one()
    assert demo.username == DEMO_USERNAME
    assert len(repository.list_transactions(demo.id)) == len(DEMO_TRANSACTIONS)
    assert {c.name for c in Category.query.all()} == {"Salary", "Housing", "Food"}


def test_seed_demo_can_run_again_without_duplicating_anything(app):
    run_seed(app)
    result = run_seed(app)
    assert result.exit_code == 0, result.output
    assert "Demo user already exists." in result.output
    assert "Sample transactions added: 0" in result.output
    assert User.query.count() == 1
    assert Transaction.query.count() == len(DEMO_TRANSACTIONS)


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
        {"type": "income", "amount": 1, "date": DEMO_TRANSACTIONS[0]["date"], "category": "Mine", "description": "", "user_id": real.id}
    )
    html = client.get("/transactions/").get_data(as_text=True)
    assert "Monthly salary" in html
    assert "Mine" not in html  # the first real user does not share the demo user's data
