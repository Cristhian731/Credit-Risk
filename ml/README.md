# ml/

This folder is intentionally empty for now. It will hold the machine learning part of
Credit Risk in later iterations:

- **Credit viability prediction**: classify whether a loan is viable from customer data
  (age, income, employment status, credit history, debt-to-income ratio, loan amount and
  term), returning a risk score and the key factors behind the decision. See
  [docs/Project_Proposal.md](../docs/Project_Proposal.md) for the methodology (CRISP-DM)
  and candidate models.
- **Spending analysis**: use the income and expense history recorded in the app for
  monthly spending forecasts and overspending risk.

Planned layout:

- `notebooks/`: exploration and experiments.
- `training/`: scripts that train and evaluate the models.
- `artifacts/`: serialized models (kept out of git if they are large).
- A small Python module that the Flask app calls to get predictions, so routes never
  depend on training code.
