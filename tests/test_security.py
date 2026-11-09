"""Tests for the session cookie settings and foreign key enforcement."""
from datetime import date
from decimal import Decimal

import pytest
from flask_migrate import upgrade
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.auth.services import register_user
from app.extensions import db
from app.models import Category, Transaction
from config import Config, DevelopmentConfig, ProductionConfig, TestingConfig


def is_sqlite():
    return db.engine.dialect.name == "sqlite"


# Session cookie

@pytest.mark.parametrize("config_class", [Config, DevelopmentConfig, TestingConfig, ProductionConfig])
def test_session_cookie_is_httponly_and_lax_everywhere(config_class):
    assert config_class.SESSION_COOKIE_HTTPONLY is True
    assert config_class.SESSION_COOKIE_SAMESITE == "Lax"


def test_session_cookie_is_secure_only_in_production():
    assert ProductionConfig.SESSION_COOKIE_SECURE is True
    assert DevelopmentConfig.SESSION_COOKIE_SECURE is False
    assert TestingConfig.SESSION_COOKIE_SECURE is False


def test_the_cookie_sent_after_login_carries_the_flags(app, client):
    app.config["AUTH_ENABLED"] = True
    register_user("ana", "ana@example.com", "a-long-password")
    response = client.post("/auth/login", data={"email": "ana@example.com", "password": "a-long-password"})
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Secure" not in cookie  # plain HTTP in development and tests


def test_production_sends_a_secure_cookie(monkeypatch, tmp_path):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "from-environment")
    monkeypatch.setattr(ProductionConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'prod.db'}")
    application = create_app("production")
    with application.test_request_context():
        from flask import session

        session["probe"] = 1
        response = application.make_response("ok")
        application.session_interface.save_session(application, session, response)
    cookie = response.headers["Set-Cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie


# Foreign keys

def test_sqlite_connections_enforce_foreign_keys(app):
    if not is_sqlite():
        pytest.skip("PostgreSQL and MySQL always enforce foreign keys")
    assert db.session.execute(text("PRAGMA foreign_keys")).scalar() == 1


@pytest.mark.parametrize("missing", ["user", "category"])
def test_an_orphan_row_is_rejected(app, missing):
    user = register_user("ana", "ana@example.com", "a-long-password")
    category = Category(name="Food", type="expense", user_id=user.id)
    db.session.add(category)
    db.session.commit()

    db.session.add(Transaction(
        type="expense", amount=Decimal("1.00"), date=date(2026, 11, 1),
        user_id=9999 if missing == "user" else user.id,
        category_id=9999 if missing == "category" else category.id,
    ))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert Transaction.query.count() == 0


def test_deleting_a_user_with_data_is_blocked(app):
    user = register_user("ana", "ana@example.com", "a-long-password")
    db.session.add(Category(name="Food", type="expense", user_id=user.id))
    db.session.commit()
    db.session.delete(user)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_migrations_turn_foreign_keys_back_on(tmp_path, monkeypatch):
    """migrations/env.py switches them off while migrating and on again afterwards."""
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'fk.db'}")
    application = create_app("testing")
    with application.app_context():
        upgrade()
        assert db.session.execute(text("PRAGMA foreign_keys")).scalar() == 1
        db.session.execute(text("INSERT INTO users (username, email, password_hash, created_at) VALUES ('a', 'a@x.com', 'x', '2026-11-08')"))
        with pytest.raises(IntegrityError):
            db.session.execute(text("INSERT INTO categories (name, type, user_id) VALUES ('Food', 'expense', 9999)"))
        db.session.rollback()
        db.session.remove()
        db.engine.dispose()
