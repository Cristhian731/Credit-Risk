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
| Application structure, layout and CI | Done |
| Transactions and dashboard | Example pages with sample data, waiting for the database models |
| Credit evaluation (`/credit/`) | Working end to end with a **placeholder model** trained on synthetic data |
| Database models | Contract defined, pending (teammate A) |
| Authentication | Contract defined, pending (teammate B); a fake login is used in development |

## Roadmap

- Replace the placeholder with a credit model trained on real data, following the CRISP-DM
  plan in [docs/Project_Proposal.md](docs/Project_Proposal.md), including explainability of
  the key decision factors.
- Store each credit evaluation in the database so users can see their history.
- Prefill "Monthly Income" and the debt-to-income ratio from the transactions the user has
  recorded, linking both parts of the platform.
- Spending forecasts and overspending risk from the recorded income and expenses.

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
| `CREDIT_MODEL_PATH` | Saved credit classifier | `ml/artifacts/credit_model.pkl` |
| `CREDIT_SCALER_PATH` | Saved feature scaler | `ml/artifacts/scaler.pkl` |

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
| `app/models.py` | SQLAlchemy models: User, Category, Transaction, Budget | Teammate A (database) |
| `app/auth/` | Login, registration, logout and `login_required` | Teammate B (authentication) |
| `tests/test_models_contract.py` | Definition of done for the models | Teammate A |
| `tests/test_auth_contract.py` | Definition of done for authentication | Teammate B |
| `tests/test_app.py`, `tests/test_credit.py`, `tests/conftest.py` | App and credit module tests, shared fixtures | Structure and app lead (@Cristhian731) |
| `ml/` | Feature schema, placeholder model and future real models | Whole team |
| `docs/` | Project proposal, requirements, diagrams and weekly progress notes | Whole team |
| `.github/` | CI, code owners and pull request template | Structure and app lead (@Cristhian731) |

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch names, commit format and the contract rules.
