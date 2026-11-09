"""Tests for the error pages and the logging setup."""
import logging

import pytest

from app import create_app
from app.extensions import db
from app.logging_config import _HANDLER_FLAG


@pytest.fixture
def failing_app(app):
    """The app with a route that crashes and real error handling (no exception propagation)."""
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/boom")
    def boom():
        raise RuntimeError("deliberate failure")

    return app


def test_unknown_page_shows_the_404_page(client):
    response = client.get("/does-not-exist")
    html = response.get_data(as_text=True)
    assert response.status_code == 404
    assert "Page not found" in html
    assert "<nav" in html  # the page keeps the site layout


def test_server_error_shows_the_500_page_and_logs_it(failing_app, caplog):
    with caplog.at_level(logging.ERROR, logger=failing_app.logger.name):
        response = failing_app.test_client().get("/boom")
    assert response.status_code == 500
    assert "Something went wrong" in response.get_data(as_text=True)
    assert any("500 on GET /boom" in record.getMessage() for record in caplog.records)
    assert any(record.exc_info for record in caplog.records)


def test_server_error_rolls_back_the_session(failing_app):
    from app.models import User

    @failing_app.route("/half-done")
    def half_done():
        db.session.add(User(username="ghost", email="ghost@example.com", password_hash="x"))
        db.session.flush()
        raise RuntimeError("fails after a flush")

    failing_app.test_client().get("/half-done")
    assert User.query.filter_by(username="ghost").count() == 0


def test_500_page_falls_back_to_plain_html_when_rendering_fails(failing_app, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("template broken")

    monkeypatch.setattr("app.errors.render_template", broken)
    response = failing_app.test_client().get("/boom")
    assert response.status_code == 500
    assert "Something went wrong" in response.get_data(as_text=True)


def test_logging_is_configured_once_per_app():
    first = create_app("testing")
    second = create_app("testing")
    handlers = [h for h in second.logger.handlers if getattr(h, _HANDLER_FLAG, False)]
    assert first.logger is second.logger  # Flask names the logger after the package
    assert len(handlers) == 1


def test_log_level_and_file_come_from_config(tmp_path, monkeypatch):
    from config import TestingConfig

    log_file = tmp_path / "app.log"
    monkeypatch.setattr(TestingConfig, "LOG_LEVEL", "WARNING", raising=False)
    monkeypatch.setattr(TestingConfig, "LOG_FILE", str(log_file), raising=False)
    application = create_app("testing")
    assert application.logger.level == logging.WARNING
    application.logger.warning("written to the file")
    for handler in application.logger.handlers:
        handler.flush()
    assert "written to the file" in log_file.read_text(encoding="utf-8")
    for handler in list(application.logger.handlers):  # release the file for the temp dir cleanup
        if getattr(handler, _HANDLER_FLAG, False):
            application.logger.removeHandler(handler)
            handler.close()
