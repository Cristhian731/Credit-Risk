"""Flask CLI commands."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import click

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Parents before children, so foreign keys are always satisfied.
TABLES = ["users", "categories", "clients", "budgets", "credit_applications", "transactions"]


def adopt_legacy_db(source, target):
    """Build ``target`` with the migrations and copy every row of ``source`` into it.

    ``source`` is a SQLite database created with ``db.create_all()`` before
    migrations existed. It is only read, never modified. Returns the number of
    rows copied per table.
    """
    source, target = Path(source).resolve(), Path(target).resolve()
    if not source.is_file():
        raise click.ClickException(f"Source database not found: {source}")
    if target.exists():
        raise click.ClickException(f"Target already exists, refusing to overwrite: {target}")

    env = {**os.environ, "DATABASE_URL": f"sqlite:///{target.as_posix()}"}
    subprocess.run(
        [sys.executable, "-m", "flask", "--app", "run", "db", "upgrade"],
        cwd=PROJECT_ROOT, env=env, check=True, capture_output=True,
    )

    copied = {}
    connection = sqlite3.connect(target)
    try:
        connection.execute("ATTACH DATABASE ? AS legacy", (f"file:{source.as_posix()}?mode=ro",))
    except sqlite3.OperationalError:  # URI filenames not enabled: plain attach (still only read)
        connection.execute("ATTACH DATABASE ? AS legacy", (str(source),))
    try:
        with connection:
            for table in TABLES:
                columns = [row[1] for row in connection.execute(f'PRAGMA main.table_info("{table}")')]
                legacy = {row[1] for row in connection.execute(f'PRAGMA legacy.table_info("{table}")')}
                shared = ", ".join(f'"{c}"' for c in columns if c in legacy)
                if shared:
                    connection.execute(f'INSERT INTO main."{table}" ({shared}) SELECT {shared} FROM legacy."{table}"')
                new = connection.execute(f'SELECT COUNT(*) FROM main."{table}"').fetchone()[0]
                old = connection.execute(f'SELECT COUNT(*) FROM legacy."{table}"').fetchone()[0] if legacy else 0
                if new != old:
                    raise click.ClickException(f"Row count mismatch in {table}: {old} -> {new}")
                copied[table] = new
    except Exception:
        connection.close()
        target.unlink(missing_ok=True)  # never leave a half-copied database behind
        raise
    connection.close()
    return copied


@click.command("adopt-legacy-db")
@click.argument("source", type=click.Path(dir_okay=False))
@click.argument("target", type=click.Path(dir_okay=False))
def adopt_legacy_db_command(source, target):
    """Create TARGET with the migrations and copy the data of the old SOURCE database."""
    copied = adopt_legacy_db(source, target)
    for table, count in copied.items():
        click.echo(f"{table}: {count} rows")
    click.echo(f"Done. Point DATABASE_URL (or instance/credit_risk.db) to {target} when you are ready.")


def register_cli(app):
    """Attach the CLI commands to the application."""
    app.cli.add_command(adopt_legacy_db_command)
