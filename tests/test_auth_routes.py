"""Tests for the authentication routes and the home page with AUTH_ENABLED=True."""
import pytest

from app.auth.services import MIN_PASSWORD_LENGTH, register_user
from app.models import User

EMAIL = "ana@example.com"
PASSWORD = "correct-horse-battery"


@pytest.fixture(autouse=True)
def enable_auth(app):
    app.config["AUTH_ENABLED"] = True


@pytest.fixture
def user(app):
    return register_user("ana", EMAIL, PASSWORD)


def login(client, password=PASSWORD, next_page=None):
    path = "/auth/login" if next_page is None else f"/auth/login?next={next_page}"
    return client.post(path, data={"email": EMAIL, "password": password})


def logged_in_user_id(client):
    with client.session_transaction() as client_session:
        return client_session.get("user_id")


# Registration

def test_register_page_shows_form(client):
    html = client.get("/auth/register").get_data(as_text=True)
    for name in ("username", "email", "password"):
        assert f'name="{name}"' in html


def test_register_creates_user_and_goes_to_login(app, client):
    response = client.post(
        "/auth/register",
        data={"username": "ana", "email": "Ana@Example.com", "password": PASSWORD},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/#login"
    assert User.query.filter_by(email=EMAIL).one().username == "ana"


@pytest.mark.parametrize(
    "data, message",
    [
        ({"username": "", "email": "", "password": ""}, "are required"),
        ({"username": "ana", "email": EMAIL, "password": "short"}, "at least"),
    ],
)
def test_register_rejects_invalid_data(client, data, message):
    response = client.post("/auth/register", data=data, follow_redirects=True)
    assert response.request.path == "/auth/register"
    assert message in response.get_data(as_text=True)
    assert User.query.count() == 0


def test_register_rejects_duplicate_email(client, user):
    response = client.post(
        "/auth/register",
        data={"username": "other", "email": EMAIL, "password": PASSWORD},
        follow_redirects=True,
    )
    assert "already registered" in response.get_data(as_text=True)


def test_register_user_rejects_short_password(app):
    with pytest.raises(ValueError):
        register_user("ana", EMAIL, "x" * (MIN_PASSWORD_LENGTH - 1))


# Login

def test_login_goes_to_dashboard(client, user):
    response = login(client)
    assert response.headers["Location"] == "/dashboard/"
    assert logged_in_user_id(client) == user.id


def test_login_returns_to_requested_page(client, user):
    response = client.get("/dashboard/")
    assert response.headers["Location"] == "/auth/login?next=/dashboard/"

    response = client.get(response.headers["Location"])
    assert response.headers["Location"] == "/?next=/dashboard/#login"

    home = client.get("/?next=/dashboard/").get_data(as_text=True)
    assert 'action="/auth/login?next=/dashboard/"' in home

    assert login(client, next_page="/dashboard/").headers["Location"] == "/dashboard/"


@pytest.mark.parametrize("next_page", ["//evil.com", "/\\evil.com", "https://evil.com"])
def test_login_ignores_external_next(client, user, next_page):
    assert login(client, next_page=next_page).headers["Location"] == "/dashboard/"


def test_login_with_wrong_password_stays_on_home(client, user):
    response = login(client, password="wrong-password", next_page="/credit/")
    assert response.headers["Location"] == "/?next=/credit/#login"
    assert logged_in_user_id(client) is None


# Home page and logout

def test_home_shows_login_card_when_anonymous(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="login"' in html
    assert "Log in to evaluate a loan" in html


def test_home_redirects_to_dashboard_when_logged_in(client, user):
    login(client)
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/dashboard/"


def test_logout_requires_post(client, user):
    login(client)
    assert client.get("/auth/logout").status_code == 405
    assert logged_in_user_id(client) == user.id

    response = client.post("/auth/logout")
    assert response.headers["Location"] == "/"
    assert logged_in_user_id(client) is None
    assert client.get("/credit/").status_code == 302
