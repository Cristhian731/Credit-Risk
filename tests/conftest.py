"""Shared pytest fixtures."""
import pytest

from app import create_app
from app.extensions import db


@pytest.fixture
def app():
    """Application using the testing config and a fresh in-memory database."""
    import app.models  # noqa: F401  (registers the models before create_all)

    application = create_app("testing")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def demo_user(app):
    """The persisted demo user that AUTH_ENABLED=False runs as (what flask seed-demo creates)."""
    from app.seed import ensure_demo_user

    user, _created = ensure_demo_user()
    return user
