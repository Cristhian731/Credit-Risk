"""Tests for the Alembic migrations: they build the schema the models describe."""
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models import Client, User
from config import TestingConfig


@pytest.fixture
def migrated_app(tmp_path, monkeypatch):
    """An app on an empty SQLite file that only migrations may fill."""
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'migrated.db'}")
    application = create_app("testing")
    with application.app_context():
        yield application
        db.session.remove()
        db.engine.dispose()


def test_create_app_does_not_create_tables(migrated_app):
    assert inspect(db.engine).get_table_names() == []


def test_there_is_a_single_migration_head(migrated_app):
    assert len(ScriptDirectory.from_config(migrated_app.extensions["migrate"].migrate.get_config()).get_heads()) == 1


def test_upgrade_creates_every_model_table(migrated_app):
    upgrade()
    tables = set(inspect(db.engine).get_table_names())
    assert set(db.metadata.tables) <= tables
    assert "alembic_version" in tables


def test_migrations_match_the_models(migrated_app):
    """Fails when a model changes without a new migration."""
    upgrade()
    with db.engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), db.metadata)
    assert differences == []


def test_downgrade_removes_every_table(migrated_app):
    upgrade()
    downgrade(revision="base")
    assert inspect(db.engine).get_table_names() == ["alembic_version"]


def _user(name):
    user = User(username=name, email=f"{name}@example.com")
    user.set_password("a-long-password")
    return user


def test_client_document_is_unique_per_user(migrated_app):
    upgrade()
    ana, luis = _user("ana"), _user("luis")
    db.session.add_all([ana, luis])
    db.session.commit()

    db.session.add(Client(full_name="Client A", document_number="123", user_id=ana.id))
    db.session.add(Client(full_name="Client B", document_number="123", user_id=luis.id))
    db.session.commit()  # same document, different users: allowed

    db.session.add(Client(full_name="Client C", document_number="123", user_id=ana.id))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
