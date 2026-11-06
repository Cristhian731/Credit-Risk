"""Tests for the database URL handling in config.py."""
import pytest

import config


@pytest.mark.parametrize(
    "url, expected",
    [
        ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("mysql://u:p@host:3306/db", "mysql+pymysql://u:p@host:3306/db"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("mysql+pymysql://u:p@host/db", "mysql+pymysql://u:p@host/db"),
        ("sqlite:///local.db", "sqlite:///local.db"),
    ],
)
def test_normalize_database_url(url, expected):
    assert config.normalize_database_url(url) == expected


def test_database_url_defaults_to_local_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert config.database_url() == config.LOCAL_DATABASE_URL


def test_database_url_reads_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql://u:p@host:3306/db")
    assert config.database_url() == "mysql+pymysql://u:p@host:3306/db"


@pytest.mark.parametrize("url", ["postgresql://u:p@localhost/db", "mysql://u:p@localhost/db"])
def test_database_drivers_are_installed(url):
    from sqlalchemy import create_engine

    # Creating the engine loads the driver without opening a connection.
    create_engine(config.normalize_database_url(url)).dispose()
