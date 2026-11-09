"""Tests for the Alembic migrations: they build the schema the models describe."""
import re

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text
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


def _insert_user_and_category(name="Food"):
    db.session.execute(text("INSERT INTO users (id, username, email, password_hash, created_at) VALUES (1, 'ana', 'ana@example.com', 'x', '2026-11-08')"))
    db.session.execute(text(f"INSERT INTO categories (name, type, user_id) VALUES ('{name}', 'expense', 1)"))
    db.session.commit()


def test_0002_enforces_one_category_per_user_and_type(migrated_app):
    upgrade(revision="0001")
    _insert_user_and_category()
    upgrade(revision="0002")

    assert db.session.execute(text("SELECT name FROM categories")).scalars().all() == ["Food"]  # data kept
    with pytest.raises(IntegrityError):
        db.session.execute(text("INSERT INTO categories (name, type, user_id) VALUES ('Food', 'expense', 1)"))
    db.session.rollback()
    db.session.execute(text("INSERT INTO categories (name, type, user_id) VALUES ('Food', 'income', 1)"))  # other type: allowed
    db.session.commit()


def test_0002_downgrade_removes_the_rule_and_keeps_the_data(migrated_app):
    upgrade()
    _insert_user_and_category()
    downgrade(revision="0001")

    db.session.execute(text("INSERT INTO categories (name, type, user_id) VALUES ('Food', 'expense', 1)"))  # duplicates allowed again
    db.session.commit()
    assert db.session.execute(text("SELECT COUNT(*) FROM categories")).scalar() == 2
    assert db.session.execute(text("SELECT COUNT(*) FROM users")).scalar() == 1


def _documented_sql():
    """The detection query and the fix statements from docs/MIGRATIONS.md, as written there."""
    from pathlib import Path

    doc = (Path(__file__).resolve().parent.parent / "docs" / "MIGRATIONS.md").read_text(encoding="utf-8")
    section = doc.split("### 0002 fails if a user has duplicate categories", 1)[1].split("## Notes", 1)[0]
    detect, fix = re.findall(r"```sql\n(.*?)```", section, re.DOTALL)
    return detect, [statement.strip() for statement in fix.split(";") if statement.strip()]


def test_the_documented_fix_lets_0002_run_on_duplicate_categories(migrated_app):
    upgrade(revision="0001")
    db.session.execute(text("INSERT INTO users (id, username, email, password_hash, created_at) VALUES (1, 'ana', 'ana@example.com', 'x', '2026-11-08'), (2, 'luis', 'luis@example.com', 'x', '2026-11-08')"))
    db.session.execute(text("INSERT INTO categories (id, name, type, user_id) VALUES (1, 'Food', 'expense', 1), (2, 'Food', 'expense', 1), (3, 'Food', 'expense', 2), (4, 'Food', 'income', 1)"))
    db.session.execute(text("INSERT INTO transactions (type, amount, date, category_id, user_id) VALUES ('expense', 5, '2026-11-01', 2, 1), ('expense', 7, '2026-11-02', 1, 1)"))
    db.session.execute(text("INSERT INTO budgets (amount, month, category_id, user_id) VALUES (100, '2026-11-01', 2, 1)"))
    db.session.commit()

    detect, fix = _documented_sql()
    assert db.session.execute(text(detect)).fetchall() == [(1, "expense", "Food", 2)]
    for statement in fix:
        db.session.execute(text(statement))
    db.session.commit()
    assert db.session.execute(text(detect)).fetchall() == []

    upgrade(revision="0002")
    assert db.session.execute(text("SELECT id FROM categories ORDER BY id")).scalars().all() == [1, 3, 4]
    assert db.session.execute(text("SELECT DISTINCT category_id FROM transactions")).scalars().all() == [1]
    assert db.session.execute(text("SELECT category_id FROM budgets")).scalar() == 1


def test_0002_stops_on_duplicate_categories_as_documented(migrated_app):
    upgrade(revision="0001")
    _insert_user_and_category()
    db.session.execute(text("INSERT INTO categories (name, type, user_id) VALUES ('Food', 'expense', 1)"))
    db.session.commit()
    with pytest.raises(IntegrityError):
        upgrade(revision="0002")
