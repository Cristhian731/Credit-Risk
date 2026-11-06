"""Tests for the application structure: factory, configuration and routes."""
import pytest

from app import create_app
from app.auth import services
from config import ProductionConfig

PAGES = [
    "/",
    "/transactions/",
    "/transactions/new",
    "/dashboard/",
    "/auth/login",
]


@pytest.fixture
def fake_auth_app(app):
    app.config["FAKE_AUTH"] = True
    return app


def test_development_config_enables_debug_and_fake_auth():
    app = create_app("development")
    assert app.debug is True
    assert app.config["FAKE_AUTH"] is True


def test_testing_config_disables_fake_auth(app):
    assert app.testing is True
    assert app.config["FAKE_AUTH"] is False


def test_production_requires_secret_key(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", None)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("production")


def test_production_disables_debug_and_fake_auth(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "from-environment")
    app = create_app("production")
    assert app.debug is False
    assert app.config["FAKE_AUTH"] is False
    assert app.config["SECRET_KEY"] == "from-environment"


@pytest.mark.parametrize("path", PAGES)
def test_page_responds_ok(fake_auth_app, path):
    response = fake_auth_app.test_client().get(path)
    assert response.status_code == 200


def test_base_layout_shows_navigation(fake_auth_app):
    html = fake_auth_app.test_client().get("/").get_data(as_text=True)
    for label in ("Home", "Transactions", "Dashboard", "Login"):
        assert label in html


def test_static_files_are_served(client):
    assert client.get("/static/css/main.css").status_code == 200
    assert client.get("/static/js/main.js").status_code == 200


def test_fake_auth_mode_returns_demo_user(fake_auth_app):
    with fake_auth_app.test_request_context():
        assert services.register_user("demo", "demo@creditrisk.local", "pw") is services.FAKE_USER
        assert services.authenticate_user("demo@creditrisk.local", "pw") is services.FAKE_USER
        assert services.authenticate_user("", "") is None
        services.logout_user()
