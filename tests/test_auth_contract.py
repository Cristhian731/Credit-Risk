"""Contract for app/auth/services.py (teammate B).

Authentication is done when every test here passes. It needs the models from
teammate A. Then remove the ``pytestmark`` xfail line below so a regression
fails the build. These tests always run with FAKE_AUTH disabled.
"""
import pytest
from flask import g, session
from werkzeug.security import check_password_hash

from app.auth.services import authenticate_user, login_required, logout_user, register_user
from app.extensions import db
from app.models import User

# TODO(teammate B): delete this marker once authentication is implemented.
pytestmark = pytest.mark.xfail(reason="Pending teammate B: implement app/auth/services.py", strict=False)

EMAIL = "ana@example.com"
PASSWORD = "correct-horse-battery"


@pytest.fixture
def user(app):
    return register_user("ana", EMAIL, PASSWORD)


def test_register_user_persists_user(user):
    assert isinstance(user, User)
    assert user.id is not None
    assert db.session.execute(db.select(User).filter_by(email=EMAIL)).scalar_one() is user


def test_register_user_stores_hashed_password(user):
    assert user.password_hash != PASSWORD
    assert PASSWORD not in user.password_hash
    assert check_password_hash(user.password_hash, PASSWORD)


@pytest.mark.parametrize("username, email", [("ana", "other@example.com"), ("other", EMAIL)])
def test_register_user_rejects_duplicates(user, username, email):
    with pytest.raises(ValueError):
        register_user(username, email, PASSWORD)


@pytest.mark.parametrize("username, email, password", [("", EMAIL, PASSWORD), ("ana", "", PASSWORD), ("ana", EMAIL, "")])
def test_register_user_rejects_empty_values(app, username, email, password):
    with pytest.raises(ValueError):
        register_user(username, email, password)


def test_authenticate_user_accepts_valid_credentials(app, user):
    with app.test_request_context():
        assert authenticate_user(EMAIL, PASSWORD) is user
        assert session["user_id"] == user.id


def test_authenticate_user_rejects_wrong_password(app, user):
    with app.test_request_context():
        assert authenticate_user(EMAIL, "wrong-password") is None
        assert "user_id" not in session


def test_authenticate_user_rejects_unknown_email(app, user):
    with app.test_request_context():
        assert authenticate_user("nobody@example.com", PASSWORD) is None
        assert "user_id" not in session


def test_logout_user_clears_session(app, user):
    with app.test_request_context():
        authenticate_user(EMAIL, PASSWORD)
        logout_user()
        assert "user_id" not in session


def test_logout_user_without_login_is_safe(app):
    with app.test_request_context():
        logout_user()


def test_login_required_redirects_anonymous_user(client):
    response = client.get("/transactions/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/login")


def test_login_required_allows_logged_in_user(client, user):
    with client.session_transaction() as client_session:
        client_session["user_id"] = user.id
    assert client.get("/transactions/").status_code == 200


def test_login_required_sets_current_user(app, user):
    @login_required
    def view():
        return g.user

    with app.test_request_context():
        session["user_id"] = user.id
        assert view() is user
