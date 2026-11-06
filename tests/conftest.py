"""Shared pytest fixtures."""
import pytest

from app import create_app
from app.extensions import db
from app.services import repository


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


@pytest.fixture(autouse=True)
def empty_repository():
    """Start every test with no stored transactions or credit applications."""
    repository.reset(seed=False)
    yield
    repository.reset(seed=False)
