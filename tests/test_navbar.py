"""Tests for the navbar in each mode and for the home redirect."""
import re

import pytest

from app.auth.services import register_user

EMAIL = "ana@example.com"
PASSWORD = "correct-horse-battery"

PUBLIC_LABELS = ("The Problem", "Objective", "How It Works", "Technologies")
APP_LABELS = ("Transactions", "Dashboard", "Credit Evaluation")


def navbar(response):
    """Return the text of the <nav> element of a response."""
    html = response.get_data(as_text=True)
    return re.search(r"<nav.*?</nav>", html, re.DOTALL).group(0)


@pytest.fixture
def auth_on(app):
    app.config["AUTH_ENABLED"] = True


@pytest.fixture
def logged_in_client(app, client, auth_on):
    register_user("ana", EMAIL, PASSWORD)
    client.post("/auth/login", data={"email": EMAIL, "password": PASSWORD})
    return client


# a) Logged out (authentication on)

def test_navbar_logged_out_shows_public_sections_login_and_register(client, auth_on):
    nav = navbar(client.get("/"))
    for label in PUBLIC_LABELS + ("Log in", "Register"):
        assert label in nav
    assert 'href="/auth/register"' in nav


def test_navbar_logged_out_hides_app_links_and_logout(client, auth_on):
    nav = navbar(client.get("/"))
    for label in APP_LABELS + ("Log out",):
        assert label not in nav


# b) Logged in (authentication on)

def test_navbar_logged_in_shows_app_links_user_name_and_logout(logged_in_client):
    nav = navbar(logged_in_client.get("/dashboard/"))
    for label in APP_LABELS + ("ana", "Log out"):
        assert label in nav


def test_navbar_logged_in_hides_public_sections_login_and_register(logged_in_client):
    nav = navbar(logged_in_client.get("/dashboard/"))
    for label in PUBLIC_LABELS + ("Log in", "Register"):
        assert label not in nav


def test_navbar_escapes_user_name(app, client, auth_on):
    register_user("<b>ana</b>", EMAIL, PASSWORD)
    client.post("/auth/login", data={"email": EMAIL, "password": PASSWORD})
    nav = navbar(client.get("/dashboard/"))
    assert "<b>ana</b>" not in nav
    assert "&lt;b&gt;ana&lt;/b&gt;" in nav


# c) Home redirect

def test_home_redirects_to_dashboard_with_session(logged_in_client):
    response = logged_in_client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/dashboard/"


def test_home_is_public_without_session(client, auth_on):
    assert client.get("/").status_code == 200


def test_home_does_not_redirect_in_demo_mode(client):
    assert client.get("/").status_code == 200


# d) Configuration defaults: see tests/test_app.py


# e) Demo mode (AUTH_ENABLED False)

def test_navbar_demo_mode_keeps_app_links(client, demo_user):
    nav = navbar(client.get("/"))
    for label in PUBLIC_LABELS + APP_LABELS + ("Log in",):
        assert label in nav
    assert "Register" not in nav
