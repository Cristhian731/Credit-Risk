# Architecture and integration guide

How the pieces of the app fit together, the contracts between them, and how to deploy.
The database and the login are integrated; this guide is the reference for changing them
without breaking the rest of the app.

## Layers

```
templates/  <-  routes (app/<blueprint>/routes.py)  ->  app/services/repository.py  ->  app/models.py
                      |                                                                    |
                      +-- app/auth/services.py (current user, login_required)              +-- migrations/
```

Rules:

- Routes never query the database directly: they call `app/services/repository.py`, which
  returns plain dicts (never SQLAlchemy objects).
- Every repository function that reads or changes a record takes the `user_id` first and only
  touches that user's records. Another user's id behaves like a missing one, so routes answer
  **404** for both (never 403).
- Nothing calculable is stored: dashboard totals are summed by the database on every read.
- Every POST form carries a CSRF token. Deleting is always a POST behind a confirmation page.
- The schema only changes through migrations (`docs/MIGRATIONS.md`).

## Contracts

### Repository (`app/services/repository.py`)

| Function | Returns |
|---|---|
| `save_transaction(data)` | the saved transaction; the category (text) is created on first use, per user and type |
| `list_transactions(user_id)` | all the user's transactions, newest date first |
| `paginate_transactions(user_id, page, per_page)` | one page: `items`, `page`, `pages`, `total`, `per_page` |
| `get_transaction(user_id, id)` / `update_transaction(user_id, id, data)` | the record, or `None` if it is not the user's |
| `delete_transaction(user_id, id)` | `True`, or `False` if it is not the user's; the category is kept |
| `transaction_totals(user_id)` | `income`, `expense`, `balance` over all the user's transactions |
| `save_credit_application(data)` | the saved evaluation; `data` carries `client_full_name` and `client_document` (the client is found by document within the user, or created) |
| `list_credit_applications(user_id, limit=None)` / `paginate_credit_applications(...)` | evaluations, newest first |
| `get_credit_application(user_id, id)` / `delete_credit_application(user_id, id)` | as for transactions; evaluations are never edited; the client is kept |
| `count_credit_applications(user_id)` | the number of evaluations |

Pages are cut by the database (`LIMIT`/`OFFSET`); an invalid page becomes 1 and a page past the
end becomes the last one.

### Authentication (`app/auth/services.py`)

- `register_user`, `authenticate_user`, `logout_user`, `get_current_user`, `login_required`.
- The logged-in user's id lives in `session["user_id"]`. Passwords are hashed with werkzeug and
  need at least 8 characters. The demo email is reserved.
- With `AUTH_ENABLED=False` every request runs as the persisted demo user
  (`get_demo_user()`, created by `flask --app run seed-demo`). Without it, protected pages
  answer 503 with that instruction.

### Models (`app/models.py`)

`User`, `Category`, `Transaction`, `Budget`, `Client`, `CreditApplication`. Unique rules:
`users.username`, `users.email`, `clients (user_id, document_number)` and
`categories (user_id, type, name)`. A model change needs a migration; a test fails otherwise.

## Commands

| Command | Purpose |
|---|---|
| `flask --app run db upgrade` | Create or update the schema |
| `flask --app run seed-demo` | Create the demo user and sample transactions (safe to run again) |
| `flask --app run adopt-legacy-db OLD NEW` | Move a database created before migrations existed |

## Tests and CI

- `pytest` runs everything on in-memory SQLite. `TEST_DATABASE_URL` runs the same suite on
  another database (CI uses PostgreSQL); use an empty database, the tests create and drop tables.
- `tests/test_e2e.py` walks the whole journey with authentication and CSRF on and an app restart.
- CI (`.github/workflows/tests.yml`) has two jobs, SQLite and PostgreSQL 17. Both run
  `flask db upgrade` on an empty database, check the head revision, downgrade to `base`, upgrade
  again, and then run the whole suite.

## Deploying on Render

Set these environment variables in the Render dashboard (**Environment** tab). Never commit
their values.

| Variable | Required | Value |
|---|---|---|
| `SECRET_KEY` | **Yes** | A long random string, e.g. `python -c "import secrets; print(secrets.token_hex(32))"`. The app refuses to start without it. |
| `DATABASE_URL` | **Yes** | The Render PostgreSQL **Internal Database URL**, e.g. `postgresql://user:password@host:5432/credit_risk`. Plain URLs are mapped to the installed drivers (psycopg, PyMySQL). Without it the app would use a SQLite file that Render erases. |
| `AUTH_ENABLED` | **Yes** | `true`. It is already the production default; setting it explicitly documents the intent. `false` is demo mode and must never hold real data. |
| `FLASK_CONFIG` | **Yes** | `production` |
| `PYTHON_VERSION` | Recommended | A **full** version of the 3.14 line that CI uses, e.g. `3.14.10` (Render rejects `3.14` here; it needs major.minor.patch). Without it, new Render services already default to 3.14. |

Commands (free plan, which has no Pre-Deploy Command):

| Setting | Value |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `flask --app run db upgrade && gunicorn run:app` |

The migrations run on every start and do nothing when the schema is already up to date. On a
paid plan, `flask --app run db upgrade` can move to the Pre-Deploy Command and the start command
becomes `gunicorn run:app`.
- Production sends the session cookie only over HTTPS (`SESSION_COOKIE_SECURE`); Render serves
  HTTPS, so nothing else is needed.
- Render only manages **PostgreSQL** databases directly; a MySQL database must come from an
  external provider. On the free plan the file system is not persistent, so a SQLite file is
  erased on every deploy: use PostgreSQL for real data.
