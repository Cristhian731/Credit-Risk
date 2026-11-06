# Integration checklist

How to plug the real database (teammate A) and the real login (teammate B) into the app
without rewriting the routes. The routes already call stable functions; each teammate only
replaces the bodies of those functions.

## Integration order

1. **Database first** (teammate A).
2. **Login second** (teammate B). It needs the `User` model.
3. **Turn authentication on last**: set `AUTH_ENABLED=True`.

Merge each step into `develop` through its own pull request, and only when the tests listed
for that step pass.

## Step 1 - Database (teammate A)

**Files to change**

- [ ] `app/models.py`: turn the templates `User`, `Category`, `Transaction`, `Budget`, `Client`
      and `CreditApplication` into Flask-SQLAlchemy models. Keep every class, table, column and
      relationship name exactly as documented.
- [ ] `app/services/repository.py`: replace the in-memory bodies of `save_transaction`,
      `list_transactions`, `save_credit_application` and `list_credit_applications` with
      database queries. Keep the signatures and keep returning plain dicts with the model column
      names plus `id`. Remove `reset()`, the demo records and the in-memory lists, and the
      `empty_repository` fixture in `tests/conftest.py` (replace it with a database cleanup if
      needed).
- [ ] Create the tables (for example with Flask-Migrate or a `flask` CLI command). Never call
      `db.create_all()` at import time.

**Tests that must pass before merging**

- [ ] `pytest tests/test_models_contract.py`, then delete its `pytestmark = pytest.mark.xfail(...)`.
- [ ] `pytest tests/test_repository.py tests/test_transactions.py tests/test_credit.py`
      (they use only the repository functions, so they must still pass with the database).
- [ ] `pytest` (whole suite) with no new failures.

## Step 2 - Login (teammate B)

**Files to change**

- [ ] `app/auth/services.py`: implement `register_user`, `authenticate_user`, `logout_user`,
      `get_current_user` and the `AUTH_ENABLED=True` branch of `login_required`. Hash passwords
      with werkzeug; store the user id in `session["user_id"]`.
- [ ] `app/auth/routes.py`: replace the placeholders `auth.login`, `auth.register` and
      `auth.logout`.
      - `auth.login` reads the form fields `email`, `password` and `remember` from
        `templates/auth/_login_form.html` (do not change that card's design or field names).
      - `auth.register` serves the "Create an account" link.
- [ ] Delete the placeholder tests that expect "Login is not available yet.":
      `test_auth_placeholders_flash_and_redirect_home` in `tests/test_app.py` and
      `test_submitting_login_shows_not_available_message` in `tests/test_home.py`.

**Tests that must pass before merging**

- [ ] `pytest tests/test_auth_contract.py`, then delete its `pytestmark = pytest.mark.xfail(...)`.
- [ ] `pytest tests/test_home.py` (the login form contract).
- [ ] `pytest` (whole suite) with no new failures.

## Step 3 - Turn authentication on

- [ ] Set `AUTH_ENABLED=True` locally and check: anonymous users are redirected to the login
      from `/transactions/`, `/dashboard/` and `/credit/`; after logging in, the pages work and the
      records saved carry the real user's id.
- [ ] Look for the `# INTEGRATION: user_id comes from authenticated user` markers
      (`app/transactions/routes.py`, `app/credit/routes.py`) and confirm they receive the real user.
- [ ] Set `AUTH_ENABLED=True` in Render.

## Pending decision: client identification

`CreditApplication.client_id` is required, but the credit form does not identify the client
yet, so the route saves `client_id=None`. Before step 1 is merged, the team must agree on how
to capture the client (proposed: add `full_name` and `document_number` to the credit form,
using the `Client` column names, and a repository function that finds or creates the client).

## Render configuration

Set these environment variables in the Render dashboard (**Environment** tab). Never commit
their values.

| Variable | Value |
|---|---|
| `DATABASE_URL` | Connection URL of the database, e.g. `postgresql://user:password@host:5432/credit_risk` or `mysql://user:password@host:3306/credit_risk`. Plain URLs are mapped to the installed drivers (psycopg, PyMySQL). |
| `SECRET_KEY` | A long random string, e.g. the output of `python -c "import secrets; print(secrets.token_hex(32))"`. Required in production. |
| `AUTH_ENABLED` | `False` until step 3 is done, then `True`. |
| `FLASK_CONFIG` | `production` |

Start command: `gunicorn run:app`

**Notes**

- Render only manages **PostgreSQL** databases directly. A MySQL database must come from an
  external provider; only `DATABASE_URL` changes.
- On Render's free plan the file system is not persistent: a local **SQLite** file is **erased on
  every deploy** (and restart). Use PostgreSQL or an external MySQL for real data.
- With `AUTH_ENABLED=False` every visitor acts as the demo user. Do not store real data in that
  mode.
