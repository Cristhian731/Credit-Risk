# Credit Risk

Credit Risk is a web platform with two goals:

1. **Financial management**: users record their income and expenses and follow their
   balance and budgets.
2. **Credit viability prediction** (future iterations): a machine learning model estimates
   whether a loan is viable from customer data such as age, income, employment status,
   credit history, debt-to-income ratio, loan amount and term. The recorded financial
   history can also feed spending forecasts and overspending risk.

The current iteration builds the application structure and the contracts between team
members; no machine learning is implemented yet. The original project proposal is in
[docs/Project_Proposal.md](docs/Project_Proposal.md).

## Getting started

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000. The development config enables a fake login (`FAKE_AUTH=true`)
so the protected pages work before real authentication exists.

Run the tests with:

```bash
pytest
```

The contract tests show as `xfailed` until the database models and authentication are
implemented.

### Configuration

| Variable | Purpose | Default |
|---|---|---|
| `FLASK_CONFIG` | `development`, `testing` or `production` | `development` |
| `SECRET_KEY` | Session signing key. **Required in production.** | insecure key in development |
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///credit_risk.db` in `instance/` |
| `FAKE_AUTH` | `true` to use the fake demo user | `true` in development, always off in testing and production |

Production example: `FLASK_CONFIG=production SECRET_KEY=... gunicorn run:app`

## Project structure

```
.
├── app/
│   ├── __init__.py          # create_app() application factory
│   ├── extensions.py        # Flask extensions (SQLAlchemy db)
│   ├── models.py            # Database model contract
│   ├── sample_data.py       # Temporary example data for the placeholder views
│   ├── main/                # Home page blueprint
│   ├── transactions/        # Transactions blueprint
│   ├── dashboard/           # Dashboard blueprint
│   └── auth/                # Authentication blueprint and services contract
├── templates/               # Jinja2 templates (base.html + one folder per blueprint)
├── static/
│   ├── css/
│   └── js/
├── ml/                      # Future machine learning work
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
| `templates/`, `static/` | Layout, pages, styles and scripts | Structure and app lead (@Cristhian731) |
| `app/models.py` | SQLAlchemy models: User, Category, Transaction, Budget | Teammate A (database) |
| `app/auth/` | Login, registration, logout and `login_required` | Teammate B (authentication) |
| `tests/test_models_contract.py` | Definition of done for the models | Teammate A |
| `tests/test_auth_contract.py` | Definition of done for authentication | Teammate B |
| `tests/test_app.py`, `tests/conftest.py` | App structure tests and shared fixtures | Structure and app lead (@Cristhian731) |
| `ml/` | Future credit viability and spending models | Whole team (later iterations) |
| `docs/` | Project proposal, requirements, diagrams and weekly progress notes | Whole team |
| `.github/` | CI, code owners and pull request template | Structure and app lead (@Cristhian731) |

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch names, commit format and the contract rules.
