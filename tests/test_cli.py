"""Tests for the flask adopt-legacy-db command."""
import sqlite3

import pytest
from alembic.script import ScriptDirectory
from click.testing import CliRunner

from app import create_app
from app.cli import PROJECT_ROOT, adopt_legacy_db_command
from app.extensions import db
from app.models import User
from config import TestingConfig


def migration_head():
    """The newest migration revision."""
    return ScriptDirectory(str(PROJECT_ROOT / "migrations")).get_current_head()


@pytest.fixture
def legacy_db(tmp_path, monkeypatch):
    """A database created with db.create_all(), as before migrations existed, with one user."""
    path = tmp_path / "legacy.db"
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{path}")
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        user = User(username="ana", email="ana@example.com")
        user.set_password("a-long-password")
        db.session.add(user)
        db.session.commit()
        db.session.remove()
        db.engine.dispose()
    return path


def test_adopt_copies_data_and_leaves_the_source_untouched(legacy_db, tmp_path):
    target = tmp_path / "migrated.db"
    before = legacy_db.read_bytes()

    result = CliRunner().invoke(adopt_legacy_db_command, [str(legacy_db), str(target)])

    assert result.exit_code == 0, result.output
    assert "users: 1 rows" in result.output
    connection = sqlite3.connect(target)
    assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (migration_head(),)
    assert connection.execute("SELECT username, email FROM users").fetchall() == [("ana", "ana@example.com")]
    connection.close()
    assert legacy_db.read_bytes() == before


def test_adopt_refuses_to_overwrite_an_existing_target(legacy_db, tmp_path):
    target = tmp_path / "existing.db"
    target.write_text("keep me")

    result = CliRunner().invoke(adopt_legacy_db_command, [str(legacy_db), str(target)])

    assert result.exit_code != 0
    assert "refusing to overwrite" in result.output
    assert target.read_text() == "keep me"


def test_adopt_fails_when_the_source_is_missing(tmp_path):
    result = CliRunner().invoke(adopt_legacy_db_command, [str(tmp_path / "nope.db"), str(tmp_path / "out.db")])
    assert result.exit_code != 0
    assert "not found" in result.output
