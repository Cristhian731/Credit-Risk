# ML phase: real credit risk models

Replace the placeholder model with three models trained on a real dataset, compare them and
use the best one as the official model of the credit evaluation page.

This document is the contract between the three work streams. Changing anything in the
**Contracts** section needs the agreement of the whole team and a test update in the same PR.

## Architecture

```
ml/data/raw/Loan_default.csv          (local only, ignored by git; see ml/data/README.md)
        |
        v
ml/dataset.py     load(path) -> DataFrame       split(df) -> X_train, X_test, y_train, y_test
        |
        v
ml/pipelines.py   build_pipeline(name)  -> unfitted sklearn Pipeline (preprocessing + model)
        |
        v
ml/train.py       python -m ml.train
                  5-fold stratified CV on train -> select_champion() -> fit on train
                  -> ml/evaluate.py evaluate(model, X_test, y_test) -> save artifacts
        |
        v
ml/artifacts/manifest.json
ml/artifacts/<model>/model.joblib
ml/artifacts/<model>/metrics.json     (validated by ml/schemas.py)
        |
        v
app/credit/services.py   ModelRegistry
        |-- predict(data, model=None)   form values -> ml.features.to_model_frame -> risk score 0-100
        |-- catalog()                   manifest + metrics for the model pages (JSON only)
        v
app/credit/routes.py     /credit/  (prediction with the official model)
                         /credit/models/          (comparison)
                         /credit/models/<name>/   (one model)
```

The web app never imports training code (`dataset`, `pipelines`, `evaluate`, `train`). It only
imports `ml.features` and `ml.schemas`, and loads the saved artifacts.

### Current state (Sprint 0)

- Everything above is a stub (`NotImplementedError`) except `ml/schemas.py`, the example
  artifacts and the model pages.
- While `ml/artifacts/manifest.json` does not exist:
  - `ModelRegistry.predict` delegates to the placeholder `PredictionService`, so `/credit/`
    behaves exactly as before;
  - the model pages read `ml/artifacts/_example/` and show an **Example data** banner.
- The placeholder (`ml/train_placeholder_model.py`, `credit_model.pkl`, `scaler.pkl`) stays
  until the real models replace it.

## Contracts

### Dataset

Loan Default Prediction Dataset (Kaggle `nikhil1e9/loan-default`, CC0), file
`Loan_default.csv`, 18 columns, target `Default` (1 = default). Download and SHA-256 check:
[ml/data/README.md](../ml/data/README.md). Tests use `tests/fixtures/loan_default_sample.csv`
(60 synthetic rows, same columns).

### Models

| Name (slug and folder) | Display name | Class imbalance |
|---|---|---|
| `logistic_regression` | Logistic Regression | `class_weight="balanced"` |
| `random_forest` | Random Forest | `class_weight="balanced"` |
| `xgboost` | XGBoost | `scale_pos_weight` = negatives / positives of the training labels |

Source of truth: `ml.schemas.MODEL_NAMES` and `DISPLAY_NAMES`. Class 1 always means default,
and every model exposes `predict_proba`.

### Feature set `v2-loan-default`

`ml.features.FEATURE_ORDER` (the form and the placeholder) is **not** changed. The models use
`FEATURE_SETS["v2-loan-default"]`, built from 9 form fields by `to_model_frame`:

| Form field | Model column | Conversion |
|---|---|---|
| `age` | `Age` | clip 18-69 |
| `monthly_income` | `Income` | TODO: x12 if the EDA confirms Income is annual |
| `employment_status` | `EmploymentType` | employed -> Full-time, self_employed -> Self-employed, unemployed -> Unemployed, retired -> Part-time |
| `years_employment` | `MonthsEmployed` | x12 |
| `credit_score` | `CreditScore` | clip 300-849 |
| `dti_ratio` | `DTIRatio` | / 100 |
| `loan_amount` | `LoanAmount` | as is |
| `loan_term` | `LoanTerm` | clip 12-60 |
| `previous_loans` | `NumCreditLines` | clip 1-4 |

Clip ranges (`ml.features.CLIP_RANGES`) are the ranges observed in the dataset, so the models
never receive values they were not trained on. `existing_debt` and `payment_history` are still
stored with each application but are not model inputs. The dataset columns InterestRate,
Education, MaritalStatus, HasMortgage, HasDependents, LoanPurpose and HasCoSigner are not used
because the form does not ask for them; expect a lower ROC AUC than models that use every column.

### Split, validation and champion

- Test split: 20 %, stratified, `random_state=42` (`ml.dataset.split`). Used **only** to report
  metrics.
- Model selection: 5-fold stratified cross-validation on the train split.
- Champion (`ml.train.select_champion`): highest mean CV ROC AUC. Every model less than 0.01
  below the best one is tied, and among the tied models the highest mean CV recall of class 1
  wins. A remaining tie goes to the first model in `MODEL_NAMES` order.
- Output: `risk_percent`, a risk score 0-100 (probability of default x 100), mapped to
  Approved / Medium Risk / High Risk with the existing thresholds in `config.py`.

### Artifacts

```
ml/artifacts/manifest.json
ml/artifacts/<model>/model.joblib     fitted Pipeline (joblib)
ml/artifacts/<model>/metrics.json
```

`manifest.json`:

```json
{
  "version": "2026-11-20.1",
  "trained_at": "2026-11-20T21:30:00Z",
  "dataset": {"name": "Loan Default Prediction Dataset", "sha256": "<64 hex>", "rows": 255347},
  "feature_set": "v2-loan-default",
  "selection_rule": "Highest mean ROC AUC in 5-fold stratified CV on the train split; ...",
  "champion": "xgboost",
  "models": ["logistic_regression", "random_forest", "xgboost"]
}
```

`<model>/metrics.json`:

```json
{
  "model": "xgboost",
  "display_name": "XGBoost",
  "model_version": "2026-11-20.1",
  "cv": {"roc_auc": [0.718, 0.004], "recall": [0.625, 0.009], "precision": [0.237, 0.003], "f1": [0.344, 0.004]},
  "test": {"roc_auc": 0.720, "recall": 0.627, "precision": 0.238, "f1": 0.345, "accuracy": 0.723},
  "confusion_matrix": [[33209, 11930], [2210, 3721]],
  "roc_curve": {"fpr": [0.0, "... about 50 points ...", 1.0], "tpr": [0.0, "...", 1.0]},
  "feature_importance": [{"feature": "Age", "importance": 0.27}],
  "params": {"n_estimators": 300, "max_depth": 4}
}
```

Rules checked by `ml.schemas.validate_artifacts`:

- `cv` values are `[mean, std]`; every metric is in [0, 1].
- `confusion_matrix` is `[[tn, fp], [fn, tp]]` at threshold 0.5, and test recall, precision,
  f1 and accuracy agree with it.
- `roc_curve` has about 50 points, non-decreasing, from (0, 0) to (1, 1).
- `feature_importance` names columns of the manifest feature set (one-hot columns are added
  back to their original column).
- `model_version` equals `manifest.version`; `champion` is one of `models`.
- Real artifacts: every `model.joblib` exists and the folder stays **under 20 MB** in total
  (limit the random forest depth, leaf size and number of trees).

`evaluate()` returns exactly the `test`, `confusion_matrix` and `roc_curve` keys
(`ml.schemas.EVALUATION_KEYS`); `train.py` adds the rest. The example in
`ml/artifacts/_example/` has fictitious but consistent numbers and shows the tie-break:
XGBoost has the best CV ROC AUC, but Logistic Regression is within 0.01 and has a higher CV
recall, so it is the champion.

### ModelRegistry (memory on Render free plan: 512 MB)

- Created at start-up but loads **no** model file then.
- `predict(data)` uses the champion of `manifest.json`; `predict(data, model=name)` uses any of the
  three models. A model file is loaded on demand, and **at most one model is kept in memory at a
  time**: loading another model releases the previous one. Without a manifest, `predict(data)`
  falls back to the placeholder model.
- The model pages use `catalog()` and `selection_summary()`, which only read JSON.
- Same output as `PredictionService.predict` (`label`, `risk_percent`, `recommendation`) plus
  `model` and `model_version` when a trained model answered. The label uses the thresholds of
  `config.py` (0.33 / 0.66) on the default probability.

### `credit_applications.model_version`

The column already exists (`String(30)`, nullable), so there is no schema change. It stores which
model made the prediction as `<code>@<manifest.version>`, with the codes of `ml.schemas.MODEL_CODES`:

| Model | Code | Example |
|---|---|---|
| `logistic_regression` | `lr` | `lr@2026-11-13.1` |
| `random_forest` | `rf` | `rf@2026-11-13.1` |
| `xgboost` | `xgb` | `xgb@2026-11-13.1` |

Evaluations made with the placeholder model keep `NULL`. The result page and the history show the
full name (`DISPLAY_NAMES`) and the version, never the code. A test checks that every code with
the manifest version fits the column length read from `app/models.py`.

### Web pages

- `/credit/models/` is **one page with four Bootstrap tabs**: Logistic Regression, Random Forest,
  XGBoost and Comparison. The tab id is the model name (or `comparison`), so `/credit/models/#xgboost`
  opens the XGBoost tab. The old `/credit/models/<name>/` redirects to its tab; an unknown name
  answers 404. All pages are `login_required`.
- Each model tab shows, from the JSON artifacts: CV and test metrics, confusion matrix, ROC curve
  and feature importance (Chart.js), selected hyperparameters, every run of `experiments.json`,
  the overfitting check and a form that predicts with **that** model (`POST
  /credit/models/<name>/predict`; the result is not saved in the history).
- The Comparison tab has the CV and test table, the overlaid ROC curves, the CV metrics chart and
  the explanation of how the champion was chosen, including the tie-break.
- Navbar: the **Credit Evaluation** menu has *New evaluation (official model)* and one link per
  tab (`/credit/models/#logistic_regression`, `#random_forest`, `#xgboost`, `#comparison`).
  History is not in the menu; it stays linked from the credit pages.
- Each model has its own partial in `templates/credit/models/` (`_logistic_regression.html`,
  `_random_forest.html`, `_xgboost.html`). The shared blocks are in `_macros.html`. Each partial
  has its **About this algorithm** section (how it works, why it fits, strengths and limits, what
  each hyperparameter does, APA 7 references). The selected hyperparameters and the metrics in the
  text are template variables read from the JSON artifacts, never typed by hand.
- The charts are drawn by `static/js/model_charts.js` from the JSON embedded in the page.
- The credit form says that amounts are in USD and that the income is the **monthly** income.

## Ownership

| Stream | Owner | Files |
|---|---|---|
| data | Teammate A | `ml/dataset.py`, `ml/evaluate.py`, `notebooks/01_eda.ipynb`, CRISP-DM section of the report; tests `test_ml_dataset.py`, `test_ml_evaluate.py` |
| ml | Cristhian | `ml/features.py` (`to_model_frame`), `ml/pipelines.py`, `ml/train.py`, `app/credit/services.py` (`ModelRegistry`), PR reviews; tests `test_ml_features.py`, `test_ml_pipelines.py`, `test_ml_train.py`, `test_model_registry.py` |
| web | Cristhian | `app/credit/routes.py` (model pages), `templates/credit/models.html`, `templates/credit/models/*.html` (the three tabs and their "About this algorithm" texts), navbar, `static/js/model_charts.js`; tests `test_credit_models_routes.py`, `test_credit_champion.py` |

Shared and protected: `ml/schemas.py` and the example artifacts (contract changes only with
team agreement); `app/models.py`, `app/services/repository.py` and `app/auth/services.py` are not
changed in this phase, and there are no schema changes.

Skeleton tests are marked `@pytest.mark.skip(reason="Sprint N - owner: data|ml|web")` and describe
the expected behaviour in their docstring. Implementing a stub means removing the skip from its
tests and making them pass; never delete a test.

## Branches

```
develop
 |- feat/ml-real-model            (Sprint 1: data and models)
 |   |- feat/ml-eda-dataset       data: EDA notebook, dataset.py
 |   |- feat/ml-evaluate          data: evaluate.py
 |   |- feat/ml-train-pipelines   ml: features.py, pipelines.py, train.py, ModelRegistry
 |- feat/credit-model-pages       (Sprint 2: web)
     |- feat/credit-model-ui      web: model pages, charts, navbar
     |- feat/credit-registry      ml: ModelRegistry per-model predictions
```

- Sub-branches open PRs into their phase branch; phase branches open PRs into `develop`.
- Keep branches up to date with `git merge develop` (or the phase branch). No rebase, no force push.
- `python -m pytest -q` must pass before every PR.
- Conventional Commits in English (`feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `build`).

## Dependencies

`pandas==3.1.1` and XGBoost 3.4.1. `xgboost-cpu` (CPU-only, much smaller) has no macOS wheels,
so `requirements.txt` uses environment markers:

```
xgboost-cpu==3.4.1; sys_platform != "darwin"
xgboost==3.4.1; sys_platform == "darwin"
```

Both install the same `xgboost` module. Train with the pinned scikit-learn and XGBoost versions:
the saved `model.joblib` files are only guaranteed to load with them.
