"""Tests with CSRF protection ON (it is off in TestingConfig for the other tests)."""
import re
from pathlib import Path

import pytest

from app.auth.services import register_user
from app.models import User

EMAIL = "ana@example.com"
PASSWORD = "correct-horse-battery"
TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


@pytest.fixture(autouse=True)
def csrf_on(app):
    app.config["WTF_CSRF_ENABLED"] = True
    app.config["AUTH_ENABLED"] = True


def token_from(client, path):
    """Open a page and return the CSRF token of its form."""
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


@pytest.fixture
def logged_in(app, client):
    register_user("ana", EMAIL, PASSWORD)
    token = token_from(client, "/")
    client.post("/auth/login", data={"email": EMAIL, "password": PASSWORD, "csrf_token": token})
    return client


def test_testing_config_has_csrf_off_by_default():
    from config import TestingConfig

    assert TestingConfig.WTF_CSRF_ENABLED is False


def test_every_post_form_carries_a_csrf_token():
    """Guard for future templates: a POST form without a token would always fail."""
    for template in TEMPLATES.rglob("*.html"):
        html = template.read_text(encoding="utf-8")
        for form in re.findall(r"<form\b.*?</form>", html, re.DOTALL | re.IGNORECASE):
            if re.search(r'method="post"', form, re.IGNORECASE):
                assert "csrf_token()" in form, f"{template.name} has a POST form without a CSRF token"


# Login

def test_login_without_token_is_rejected(client):
    register_user("ana", EMAIL, PASSWORD)
    response = client.post("/auth/login", data={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 400
    assert "Invalid or expired form" in response.get_data(as_text=True)
    with client.session_transaction() as client_session:
        assert "user_id" not in client_session


def test_login_with_token_works(client):
    user = register_user("ana", EMAIL, PASSWORD)
    token = token_from(client, "/")
    response = client.post("/auth/login", data={"email": EMAIL, "password": PASSWORD, "csrf_token": token})
    assert response.status_code == 302
    with client.session_transaction() as client_session:
        assert client_session["user_id"] == user.id


def test_login_with_a_wrong_token_is_rejected(client):
    register_user("ana", EMAIL, PASSWORD)
    token_from(client, "/")
    response = client.post(
        "/auth/login", data={"email": EMAIL, "password": PASSWORD, "csrf_token": "forged"}
    )
    assert response.status_code == 400


# Registration

def test_register_without_token_is_rejected(client):
    response = client.post("/auth/register", data={"username": "ana", "email": EMAIL, "password": PASSWORD})
    assert response.status_code == 400
    assert User.query.count() == 0


def test_register_with_token_creates_the_user(client):
    token = token_from(client, "/auth/register")
    response = client.post(
        "/auth/register",
        data={"username": "ana", "email": EMAIL, "password": PASSWORD, "csrf_token": token},
    )
    assert response.status_code == 302
    assert User.query.count() == 1


# A data form (transactions) and logout

def test_new_transaction_without_token_is_rejected(logged_in):
    response = logged_in.post(
        "/transactions/new",
        data={"type": "income", "amount": "100", "date": "2026-11-01", "category": "Salary"},
    )
    assert response.status_code == 400


def test_new_transaction_with_token_is_saved(logged_in):
    token = token_from(logged_in, "/transactions/new")
    response = logged_in.post(
        "/transactions/new",
        data={"type": "income", "amount": "100", "date": "2026-11-01", "category": "Salary", "csrf_token": token},
    )
    assert response.status_code == 302


def test_logout_without_token_keeps_the_session(logged_in):
    assert logged_in.post("/auth/logout").status_code == 400
    assert logged_in.get("/dashboard/").status_code == 200


def test_logout_with_token_ends_the_session(logged_in):
    token = token_from(logged_in, "/dashboard/")
    response = logged_in.post("/auth/logout", data={"csrf_token": token})
    assert response.status_code == 302
    assert logged_in.get("/dashboard/").status_code == 302
