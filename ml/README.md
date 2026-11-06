# ml/

Machine learning code for Credit Risk. The web app only loads the saved artifacts; it never
imports training code.

## Contents

| Path | Purpose |
|---|---|
| `features.py` | Feature schema shared with the app: `FEATURE_ORDER`, categorical encodings and artifact paths |
| `train_placeholder_model.py` | Trains a **placeholder** logistic regression on synthetic data |
| `artifacts/credit_model.pkl`, `artifacts/scaler.pkl` | Saved placeholder classifier and scaler used by `app/credit/` |

Regenerate the placeholder artifacts from the project root:

```bash
python -m ml.train_placeholder_model
```

The placeholder predictions are **not** meaningful; they only let the credit evaluation page
work end to end.

## Rules for any new model

- Use the columns in `ml.features.FEATURE_ORDER`, in that order.
- Class `1` means "default / not viable"; the classifier must expose `predict_proba`.
- Save the scaler and classifier to the paths in `ml.features` (or update `config.py`).
- Protected attributes such as gender are not used as features.
- Train with the scikit-learn version pinned in `requirements.txt`.

## Roadmap

- **Credit viability prediction**: replace the placeholder with a model trained on real
  customer data following the CRISP-DM process in
  [docs/Project_Proposal.md](../docs/Project_Proposal.md): cleaning, feature engineering,
  class-imbalance treatment, comparison of logistic regression, random forest and XGBoost
  (AUC-ROC, recall, F1), and explainability of the key decision factors.
- **Spending analysis**: use the income and expense history recorded in the app for monthly
  spending forecasts and overspending risk.

Planned additions: `notebooks/` for exploration and `training/` for the real pipeline.
