# Credit Risk

Credit Risk is a web platform with two goals:

1. **Financial management**: users record their income and expenses and follow their balance and budgets.
2. **Credit risk estimate**: a machine learning model trained on a public loan dataset estimates the probability
   that an applicant defaults and returns a risk label (Approved, Medium Risk or High Risk). Both parts are linked:
   the credit form can be prefilled from the user's own transactions.

It is a university prototype (Machine Learning course, Universidad de Cundinamarca). The estimate supports a
decision; it is **not** a lending decision. The dataset looks semi-synthetic and the age finding of the evaluation
must be reviewed before any real use.

| | |
|---|---|
| **Published application** | DEPLOY_URL_PENDING (free Render plan: the first request after 15 minutes of inactivity takes about a minute) |
| **Demo account** | `demo@creditrisk.local` and the password shown on the public Methodology overview (`DEMO_PASSWORD`) |
| **Notebook (Google Colab)** | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Cristhian731/Credit-Risk/blob/main/notebooks/credit_risk_dimensionality.ipynb) |
| **Methodology (no login)** | `/methodology/`: overview and one page for each CRISP-ML phase |

## What is built

| Module | What it does |
|---|---|
| Transactions and dashboard | Income and expenses saved in the database (edit, delete, pagination); totals are calculated when read, never stored |
| Credit evaluation (`/credit/`) | The **champion** model (chosen by a documented rule) predicts from 9 form fields; each evaluation is saved with its customer and model version and listed in `/credit/history` |
| Finance to risk (`/credit/?source=finance`) | Prefills the monthly income and the debt-to-income ratio from the user's last complete months |
| Model pages (`/credit/models/`) | Four tabs (Logistic Regression, Random Forest, XGBoost, Comparison) with metrics, confusion matrix, ROC curve, feature importance, every experiment run and an "About this algorithm" text; each tab can predict with its own model |
| Methodology (`/methodology/`) | The six CRISP-ML(Q) phases, written from the JSON artifacts: every figure on the pages is read from `ml/artifacts/*.json` |
| Monitoring | Prediction log (JSON lines, no customer name or document, 90-day retention) and `python -m ml.monitor` (PSI against the train distribution) |
| Authentication and security | Registration, login, logout; CSRF on every form; HttpOnly + SameSite session cookie (Secure in production); other users' records answer 404 |

## Architecture

```
ml/data/raw/Loan_default.csv  (not in git)
        |  python -m ml.train   (5-fold CV on train only, champion rule, test split used once)
        v
ml/artifacts/  manifest.json, <model>/model.joblib + metrics.json, data_report.json, experiments.json,
               overfitting.json, subgroups.json, dimensionality_report.json,
               reference_distribution.json, monitoring_report.json        <- single source of truth
        |
        v
app/credit/services.py  ModelRegistry (loads one model at a time, on demand)
        |-- /credit/                  champion prediction + database + prediction log
        |-- /credit/models/           model pages
        '-- /methodology/phase-1..6   pages read from the JSON files
```

The web app never imports the training code. The JSON files are the source of truth: the pages, this README and the
technical report show the same numbers because they read the same files.

## The six CRISP-ML(Q) phases

| Phase | Where it lives |
|---|---|
| 1. Business and data understanding | `/methodology/phase-1`; `ml/artifacts/data_report.json` |
| 2. Data engineering | `/methodology/phase-2`; `ml/dataset.py`, `ml/features.py`; EDA, PCA and t-SNE in the Colab notebook (`dimensionality_report.json`) |
| 3. Model engineering | `/methodology/phase-3`; `ml/pipelines.py`, `ml/train.py`; `experiments.json` (every hyperparameter run) |
| 4. Evaluation | `/methodology/phase-4`; `metrics.json`, `overfitting.json`, `subgroups.json` (age and employment findings) and the domain expert review (`docs/expert_review.md`) |
| 5. Deployment | `/methodology/phase-5`; `render.yaml`, this README, the credit pages |
| 6. Monitoring and maintenance | `/methodology/phase-6`; `ml/monitor.py`, the prediction log and its retention policy |

## Reproduce the results

Use Python 3.14 (what CI and Render use). Train with the versions pinned in `requirements.txt`: the saved
`model.joblib` files are only guaranteed to load with them.

```bash
python -m venv venv
venv\Scripts\activate                 # Windows   (source venv/bin/activate on macOS / Linux)
pip install -r requirements.txt
```

1. **Dataset.** Download `Loan_default.csv` from the Kaggle [Loan Default Prediction Dataset](https://www.kaggle.com/datasets/nikhil1e9/loan-default)
   (CC0, 255,347 rows, 18 columns) into `ml/data/raw/` and check its **SHA-256**:
   `1d7556a9071e7f9e872dc05a0cad174229fb1164b1cf3470ad35eed195c24278` (the value recorded in `ml/artifacts/manifest.json`;
   commands for every platform in [ml/data/README.md](ml/data/README.md)). If it differs, do not train.
2. **Train and select the champion** (about 5 minutes; searches hyperparameters on the train split only and writes the files of `ml/artifacts/`):
   ```bash
   python -m ml.train
   ```
3. **Notebook** (EDA, PCA, t-SNE, PCA and "without Age" experiments): open it in Colab with the badge above, or locally
   with `pip install -r requirements-notebook.txt` (Python 3.12 or newer). It writes `ml/artifacts/dimensionality_report.json`
   and the figures in `static/img/methodology/`.
4. **Monitoring:**
   ```bash
   python -m ml.monitor --build-reference             # reference_distribution.json (statistics only)
   python -m ml.monitor --simulated                   # a SIMULATED batch with intentional drift
   python -m ml.monitor --log logs/predictions.jsonl  # a real batch: the prediction log of the app
   ```
   A log with fewer than 500 predictions gets a warning in the report: its PSI is mostly sampling noise.
5. **Tests:**
   ```bash
   python -m pytest -q                                # in-memory SQLite
   TEST_DATABASE_URL=postgresql://user:password@localhost:5432/credit_risk_test python -m pytest -q   # same suite on PostgreSQL
   ```
   `tests/test_e2e.py` walks the whole journey with authentication and CSRF on. CI runs the suite on SQLite and
   PostgreSQL, after migrating an empty database in both.

## Run it locally

```bash
flask --app run db upgrade     # creates the database tables (first run only)
flask --app run seed-demo      # demo account and sample transactions (safe to repeat)
python run.py
```

Open http://127.0.0.1:5000. In development authentication is on: register, log in and you land on the dashboard.
`AUTH_ENABLED=false` runs as the demo user instead. The schema is managed with migrations
([docs/MIGRATIONS.md](docs/MIGRATIONS.md)).

The **demo account** is `demo@creditrisk.local`; its password is the `DEMO_PASSWORD` environment variable
(`demo-password-2026` in development and tests; **required** in production). `seed-demo` sets that password every
time it runs, and the public Methodology overview shows the e-mail and the password. The account is shared and public
on purpose: never store real data in it.

## Deploy on Render

`render.yaml` is a Blueprint for one **free** web service and one **free** PostgreSQL database.

1. In Render choose **New > Blueprint**, connect the GitHub repository and the branch to deploy (`main`).
2. When it asks for `DEMO_PASSWORD`, type the password of the demo account (it is not stored in the repository).
   `SECRET_KEY` is generated, `DATABASE_URL` comes from the database, and `FLASK_CONFIG=production` and
   `PYTHON_VERSION=3.14.10` are set.
3. Render runs `pip install -r requirements.txt` and starts the service with
   `flask --app run db upgrade && flask --app run seed-demo && gunicorn --workers 1 --timeout 120 --bind 0.0.0.0:$PORT run:app`.
   The migrations and `seed-demo` can run on every start: they change nothing when everything is up to date, and
   `seed-demo` only refreshes the demo password. One worker keeps the memory under the 512 MB of the free plan (the
   registry keeps at most one model in memory).

Free plan limits to know: the service spins down after 15 minutes without traffic (about one minute to wake up); the file
system is not persistent, so the prediction log (`logs/predictions.jsonl`) is erased on every restart; and the free
PostgreSQL database **expires 30 days after it is created** (14 more days before it is deleted). Create it again and the
next start migrates and seeds it. More in [docs/INTEGRATION.md](docs/INTEGRATION.md).

## Commands

| Command | Purpose |
|---|---|
| `flask --app run db upgrade` | Create or update the database schema |
| `flask --app run seed-demo` | Create the demo user and its sample transactions, and set its password to `DEMO_PASSWORD` (safe to run again) |
| `flask --app run purge-prediction-log` | Delete the prediction log entries older than `PREDICTION_LOG_RETENTION_DAYS` |
| `python -m ml.monitor --simulated` | PSI of a SIMULATED batch against the train distribution; writes `ml/artifacts/monitoring_report.json` |
| `python -m ml.monitor --log logs/predictions.jsonl` | The same with the real prediction log |
| `python -m ml.monitor --build-reference` | Rebuild `ml/artifacts/reference_distribution.json` from the dataset (statistics only) |
| `flask --app run adopt-legacy-db OLD NEW` | Move a database created before migrations existed (see [docs/MIGRATIONS.md](docs/MIGRATIONS.md)) |

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `FLASK_CONFIG` | `development`, `testing` or `production` | `development` |
| `SECRET_KEY` | Session signing key. **Required in production.** | insecure key in development |
| `DATABASE_URL` | Database connection URL (PostgreSQL or MySQL, see below) | `sqlite:///credit_risk.db` in `instance/` |
| `AUTH_ENABLED` | Authentication switch (see below) | `True` in development and production, `False` in testing |
| `TEST_DATABASE_URL` | Database for the test suite (an empty one; tests create and drop tables) | in-memory SQLite |
| `LOG_LEVEL`, `LOG_FILE` | Log level and optional rotating log file | `INFO`, none |
| `DEMO_PASSWORD` | Password of the demo account, set by `seed-demo` and shown in the Methodology overview. **Required in production** (no default there) | `demo-password-2026` in development and tests |
| `PREDICTION_LOG_PATH` | JSON lines log of the predictions of the trained models (no customer name or document; ignored by git). Empty turns it off | `logs/predictions.jsonl` (off in tests) |
| `PREDICTION_LOG_RETENTION_DAYS` | Days that the prediction log is kept (see Phase 6 of the Methodology) | `90` |
| `CREDIT_MODEL_PATH` | Saved credit classifier | `ml/artifacts/credit_model.pkl` |
| `CREDIT_SCALER_PATH` | Saved feature scaler | `ml/artifacts/scaler.pkl` |

Production example: `FLASK_CONFIG=production SECRET_KEY=... DATABASE_URL=... DEMO_PASSWORD=... gunicorn --workers 1 run:app`

## Authentication switch: `AUTH_ENABLED`

| Value | Behavior |
|---|---|
| `False` (default in testing) | `login_required` lets every request through and `get_current_user()` runs as the persisted demo user (`demo@creditrisk.local`) created by `flask --app run seed-demo`; without it the pages answer 503 with that instruction. |
| `True` (default in development and production; also `1`, `yes`, `on`) | The real implementation in `app/auth/services.py` is used: protected pages (`/transactions/`, `/dashboard/`, `/credit/`) require logging in. After logging in the user goes to the page they asked for, or to `/dashboard/`; the home page redirects logged-in users to the dashboard. Passwords need at least 8 characters. |

Example (PowerShell): `$env:AUTH_ENABLED = "true"; python run.py`. See also
[docs/INTEGRATION.md](docs/INTEGRATION.md).
With `False`, every visitor acts as the demo user, so do not store real data in that mode. With `True` the demo
account is a normal account whose password is `DEMO_PASSWORD`; it is public, so it holds only sample data, and the
data of the demo user is never shown to real users.

## Database URL

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
│   ├── extensions.py        # Flask extensions: SQLAlchemy, Flask-Migrate, CSRF; SQLite foreign keys
│   ├── errors.py            # 400 (CSRF), 404, 500 and 503 pages
│   ├── logging_config.py    # Log handlers
│   ├── cli.py, seed.py      # flask seed-demo and flask adopt-legacy-db
│   ├── models.py            # Database model contract
│   ├── services/
│   │   └── repository.py    # Data access layer (SQLAlchemy): the only place routes read and write data
│   ├── main/                # Home page blueprint
│   ├── transactions/        # Transactions blueprint
│   ├── dashboard/           # Dashboard blueprint
│   ├── credit/              # Credit evaluation blueprint: form validation, predictor, model registry and prediction log
│   ├── methodology/         # Public Methodology pages: overview and the six CRISP-ML phases
│   └── auth/                # Authentication blueprint and services contract
├── templates/               # Jinja2 templates (base.html + one folder per blueprint)
├── static/
│   ├── css/
│   └── js/
├── migrations/              # Alembic migrations (see docs/MIGRATIONS.md)
├── ml/                      # Feature schema, training pipeline, monitoring and the JSON artifacts
├── tests/                   # pytest suite, including the contract tests
├── docs/                    # Project documentation
├── .github/                 # CI workflow, code owners, pull request template
├── config.py                # Development, testing and production settings
├── render.yaml              # Render Blueprint (free web service + free PostgreSQL)
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
| The rest of `tests/` | App, pages, repository, migrations, security, pagination and end-to-end tests, shared fixtures | Structure and app lead (@Cristhian731) |
| `ml/` | Feature schema, training pipeline, champion selection, monitoring and the saved artifacts | Structure and app lead (@Cristhian731) |
| `docs/` | Project proposal, architecture and integration guide, migrations, requirements and progress notes | Whole team |
| `.github/` | CI, code owners and pull request template | Structure and app lead (@Cristhian731) |

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch names, commit format and the contract rules.
