# Credit Risk

Credit Risk is a web platform with two goals:

1. **Financial management**: users record their income and expenses and follow their
   balance and budgets.
2. **Credit viability prediction**: a machine learning model estimates whether a loan is
   viable from customer data (age, income, employment status, credit history,
   debt-to-income ratio, loan amount and term) and returns a risk label, the default
   probability and a recommendation.

## Current status

| Module | Status |
|---|---|
| Application structure, Bootstrap layout and CI | Done |
| Home page with login card | Done; the login form is interface only |
| Transactions and dashboard | Working; saved in the database through `app/services/repository.py`; transactions can be edited and deleted (with confirmation); totals are calculated when the dashboard is read |
| Credit evaluation (`/credit/`) | Working end to end with a **placeholder model** trained on synthetic data; each evaluation is saved with its customer (name and document) and listed in `/credit/history`, where it can be deleted (evaluations are never edited) |
| Database | Models and migrations (`migrations/`); categories and customers are created the first time they are used |
| Authentication | Done: registration, login and logout backed by the `users` table; on by default in development (`AUTH_ENABLED=False` uses a demo user) |

See [docs/INTEGRATION.md](docs/INTEGRATION.md) for the steps to plug in the database and the login.

## Roadmap

- Replace the placeholder with a credit model trained on real data, following the CRISP-DM
  plan in [docs/Project_Proposal.md](docs/Project_Proposal.md), including explainability of
  the key decision factors.
- Prefill "Monthly Income" and the debt-to-income ratio from the transactions the user has
  recorded, linking both parts of the platform.
- Spending forecasts and overspending risk from the recorded income and expenses.

## Getting started

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
flask --app run db upgrade     # creates the database tables (first run only)
python run.py
```

The schema is managed with migrations; see [docs/MIGRATIONS.md](docs/MIGRATIONS.md) (including how to move a
database created before migrations existed).

Open http://127.0.0.1:5000. In development authentication is on by default: register, log in
and you land on the dashboard. Set `AUTH_ENABLED=false` to run as the demo user instead, after creating it with
`flask --app run seed-demo` (it also loads a few sample transactions; running it again adds nothing).

Run the tests with:

```bash
pytest
```

The authentication tests (`tests/test_auth_contract.py`, `tests/test_auth_routes.py`) run
with `AUTH_ENABLED=True`.

### Configuration

| Variable | Purpose | Default |
|---|---|---|
| `FLASK_CONFIG` | `development`, `testing` or `production` | `development` |
| `SECRET_KEY` | Session signing key. **Required in production.** | insecure key in development |
| `DATABASE_URL` | Database connection URL (PostgreSQL or MySQL, see below) | `sqlite:///credit_risk.db` in `instance/` |
| `AUTH_ENABLED` | Authentication switch (see below) | `True` in development, `False` in testing and production |
| `CREDIT_MODEL_PATH` | Saved credit classifier | `ml/artifacts/credit_model.pkl` |
| `CREDIT_SCALER_PATH` | Saved feature scaler | `ml/artifacts/scaler.pkl` |

Production example: `FLASK_CONFIG=production SECRET_KEY=... gunicorn run:app`

### Authentication switch: `AUTH_ENABLED`

| Value | Behavior |
|---|---|
| `False` (default in testing and production) | `login_required` lets every request through and `get_current_user()` runs as the persisted demo user (`demo@creditrisk.local`) created by `flask --app run seed-demo`; without it the pages answer 503 with that instruction. |
| `True` (default in development; also `1`, `yes`, `on`) | The real implementation in `app/auth/services.py` is used: protected pages (`/transactions/`, `/dashboard/`, `/credit/`) require logging in. After logging in the user goes to the page they asked for, or to `/dashboard/`; the home page redirects logged-in users to the dashboard. Passwords need at least 8 characters. |

Example (PowerShell): `$env:AUTH_ENABLED = "true"; python run.py`. See also
[docs/INTEGRATION.md](docs/INTEGRATION.md).
With `False`, every visitor acts as the demo user, so do not store real data in that mode. Nobody can log in as the
demo user (its password is random) and its data is never shown to real users.

### Database URL

Only `DATABASE_URL` changes between databases; credentials are never written in the code.

```
postgresql://user:password@host:5432/credit_risk   # PostgreSQL (psycopg driver)
mysql://user:password@host:3306/credit_risk        # MySQL (PyMySQL driver)
```

Plain `postgres://`, `postgresql://` and `mysql://` URLs are mapped to the installed drivers.

## Project structure

```
.
├── app/
│   ├── __init__.py          # create_app() application factory
│   ├── extensions.py        # Flask extensions (SQLAlchemy db)
│   ├── models.py            # Database model contract
│   ├── services/
│   │   └── repository.py    # Data access layer (SQLAlchemy): the only place routes read and write data
│   ├── main/                # Home page blueprint
│   ├── transactions/        # Transactions blueprint
│   ├── dashboard/           # Dashboard blueprint
│   ├── credit/              # Credit evaluation blueprint: form validation and predictor
│   └── auth/                # Authentication blueprint and services contract
├── templates/               # Jinja2 templates (base.html + one folder per blueprint)
├── static/
│   ├── css/
│   └── js/
├── ml/                      # Feature schema, training scripts and saved model artifacts
├── tests/                   # pytest suite, including the contract tests
├── docs/                    # Project documentation
├── .github/                 # CI workflow, code owners, pull request template
├── config.py                # Development, testing and production settings
├── run.py                   # Entry point
└── requirements.txt
```

| Path | Contents | Owner |
|---|---|---|
| `app/__init__.py`, `app/extensions.py`, `config.py`, `run.py` | Application factory, configuration and entry point | Structure and app lead (@Cristhian731) |
| `app/main/`, `app/transactions/`, `app/dashboard/` | Blueprints with the routes for each feature | Structure and app lead (@Cristhian731) |
| `app/credit/` | Credit evaluation routes, form validation and prediction service | Structure and app lead (@Cristhian731) |
| `templates/`, `static/` | Layout, pages, styles and scripts | Structure and app lead (@Cristhian731) |
| `app/models.py` | SQLAlchemy models: User, Category, Transaction, Budget, Client, CreditApplication | Teammate A (database) |
| `app/services/repository.py` | Data access functions used by the routes (database queries) | Teammate A (database) |
| `app/auth/services.py`, `app/auth/routes.py` | Login, registration, logout, `get_current_user` and `login_required` | Teammate B (authentication) |
| `templates/auth/_login_form.html` | Login card on the home page (its design and field names are fixed) | Structure and app lead (@Cristhian731); behavior by teammate B |
| `tests/test_models_contract.py` | Definition of done for the models | Teammate A |
| `tests/test_auth_contract.py` | Definition of done for authentication | Teammate B |
| `tests/test_app.py`, `tests/test_home.py`, `tests/test_credit.py`, `tests/test_transactions.py`, `tests/test_repository.py`, `tests/test_config.py`, `tests/conftest.py` | App, page, repository and configuration tests, shared fixtures | Structure and app lead (@Cristhian731) |
| `ml/` | Feature schema, placeholder model and future real models | Whole team |
| `docs/` | Project proposal, integration checklist, requirements and progress notes | Whole team |
| `.github/` | CI, code owners and pull request template | Structure and app lead (@Cristhian731) |

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch names, commit format and the contract rules.
