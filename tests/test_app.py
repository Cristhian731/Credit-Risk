"""Tests for the application structure: factory, configuration and routes."""

import pytest
from flask import g

from app import create_app
from app.auth import services
from config import DevelopmentConfig, ProductionConfig, TestingConfig

PAGES = [
    "/",
    "/transactions/",
    "/transactions/new",
    "/dashboard/",
    "/credit/",
]


def test_development_config_enables_debug():
    app = create_app("development")
    assert app.debug is True


@pytest.mark.parametrize("config_class", [DevelopmentConfig, ProductionConfig])
def test_auth_is_enabled_by_default_in_development_and_production(config_class):
    assert config_class.AUTH_ENABLED is True


def test_auth_is_disabled_by_default_only_in_testing():
    assert TestingConfig.AUTH_ENABLED is False


def test_production_app_requires_login_without_any_setting(monkeypatch, tmp_path):
    """A deploy that forgets AUTH_ENABLED gets the real login, not demo mode."""
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "from-environment")
    monkeypatch.setattr(ProductionConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'prod.db'}")
    application = create_app("production")
    assert application.config["AUTH_ENABLED"] is True
    response = application.test_client().get("/dashboard/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/login")


@pytest.mark.parametrize(
    "value, expected",
    [("true", True), ("True", True), ("1", True), ("yes", True), ("on", True),
     ("false", False), ("0", False), ("no", False), ("", False)],
)
def test_env_flag_values(monkeypatch, value, expected):
    from config import _env_flag

    monkeypatch.setenv("AUTH_ENABLED", value)
    assert _env_flag("AUTH_ENABLED", False) is expected


def test_production_requires_secret_key(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", None)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("production")


def test_production_disables_debug(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "from-environment")
    app = create_app("production")
    assert app.debug is False
    assert app.config["SECRET_KEY"] == "from-environment"


@pytest.mark.parametrize("path", PAGES)
def test_page_responds_ok_with_auth_disabled(client, demo_user, path):
    assert client.get(path).status_code == 200


def test_base_layout_shows_navigation(client, demo_user):
    html = client.get("/").get_data(as_text=True)

    for anchor in (
        "problem",
        "objective",
        "how-it-works",
        "technologies",
        "login",
    ):
        assert f'href="/#{anchor}"' in html

    for label in ("Transactions", "Dashboard", "Credit Evaluation", "Log in"):
        assert label in html


def test_static_files_are_served(client):
    assert client.get("/static/css/main.css").status_code == 200
    assert client.get("/static/js/main.js").status_code == 200


def test_auth_disabled_uses_the_persisted_demo_user(app, demo_user):
    with app.test_request_context():
        user = services.get_current_user()
        assert user.id == demo_user.id
        assert (user.username, user.email) == (services.DEMO_USERNAME, services.DEMO_EMAIL)


def test_auth_disabled_without_demo_user_has_no_current_user(app):
    with app.test_request_context():
        assert services.get_current_user() is None


def test_login_required_passes_with_auth_disabled(app, demo_user):
    @services.login_required
    def view():
        return g.user

    with app.test_request_context():
        assert view().id == demo_user.id


@pytest.mark.parametrize("path", ["/transactions/", "/dashboard/", "/credit/", "/credit/history"])
def test_demo_mode_without_demo_user_shows_how_to_create_it(client, path):
    response = client.get(path)
    assert response.status_code == 503
    assert "flask --app run seed-demo" in response.get_data(as_text=True)
