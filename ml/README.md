# ml/

Machine learning code for Credit Risk. The ML phase (real models) is described in
[docs/ML_PHASE.md](../docs/ML_PHASE.md). The web app only loads the saved artifacts; it never
imports training code.

## Contents

| Path | Purpose |
|---|---|
| `features.py` | Feature schema shared with the app: `FEATURE_ORDER`, categorical encodings and artifact paths |
| `train_placeholder_model.py` | Trains a **placeholder** logistic regression on synthetic data |
| `artifacts/credit_model.pkl`, `artifacts/scaler.pkl` | Saved placeholder classifier and scaler used by `app/credit/` |
| `schemas.py` | Format and validators of the training artifacts (`manifest.json`, `metrics.json`) |
| `dataset.py`, `pipelines.py`, `evaluate.py`, `train.py` | Real training pipeline (ML phase, stubs for now) |
| `artifacts/_example/` | Fictitious example artifacts used by the model pages until real ones exist |
| `data/` | Dataset documentation; raw files go in `data/raw/` (ignored by git) |

## Rules for the real models (ML phase)

The contracts are in [docs/ML_PHASE.md](../docs/ML_PHASE.md); this is a summary.

- Inputs come from `ml.features.FEATURE_SETS` (currently `v2-loan-default`), built from the form
  values by `ml.features.to_model_frame`. `FEATURE_ORDER` only describes the form and the
  placeholder model.
- Each model is saved as a single fitted scikit-learn `Pipeline` (preprocessing and classifier
  together) in `artifacts/<model>/model.joblib`; there is no separate scaler file.
- Class `1` means "default / not viable"; the pipeline must expose `predict_proba`.
- `artifacts/manifest.json` and `artifacts/<model>/metrics.json` must pass
  `ml.schemas.validate_artifacts`, and all artifacts together stay under 20 MB.
- The champion is chosen with cross-validation on the train split, never with the test split.
- Protected attributes such as gender are not used as features.
- Train with the scikit-learn and XGBoost versions pinned in `requirements.txt`.

## Placeholder model (legacy)

Used by `app/credit/` until `artifacts/manifest.json` exists. Regenerate its artifacts from the
project root:

```bash
python -m ml.train_placeholder_model
```

The placeholder predictions are **not** meaningful; they only let the credit evaluation page
work end to end. Its rules:

- Columns in `ml.features.FEATURE_ORDER`, in that order.
- Scaler and classifier saved separately to `MODEL_PATH` and `SCALER_PATH` in `ml.features`
  (or the paths set in `config.py`).

## Roadmap

- **Credit viability prediction**: replace the placeholder with a model trained on real
  customer data following the CRISP-DM process in
  [docs/Project_Proposal.md](../docs/Project_Proposal.md): cleaning, feature engineering,
  class-imbalance treatment, comparison of logistic regression, random forest and XGBoost
  (AUC-ROC, recall, F1), and explainability of the key decision factors.
- **Spending analysis**: use the income and expense history recorded in the app for monthly
  spending forecasts and overspending risk.

Planned additions: `notebooks/` for exploration (EDA). The real pipeline lives in this folder.
