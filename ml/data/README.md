# ml/data/

Datasets used to train the credit risk models. Raw files live in `ml/data/raw/`, which is
ignored by git: every team member downloads them locally.

## Loan Default Prediction Dataset

| Item | Value |
|---|---|
| Source | Kaggle, `nikhil1e9/loan-default`: <https://www.kaggle.com/datasets/nikhil1e9/loan-default> |
| License | CC0: Public Domain |
| File | `Loan_default.csv` |
| Columns (18) | LoanID, Age, Income, LoanAmount, CreditScore, MonthsEmployed, NumCreditLines, InterestRate, LoanTerm, DTIRatio, Education, EmploymentType, MaritalStatus, HasMortgage, HasDependents, LoanPurpose, HasCoSigner, Default |
| Target | `Default` (1 = the borrower defaulted) |

### Download

1. Download the dataset from the Kaggle page above (a free Kaggle account is required), or with
   the Kaggle CLI: `kaggle datasets download -d nikhil1e9/loan-default --unzip -p ml/data/raw`.
2. Place the file at `ml/data/raw/Loan_default.csv`.

### Verify the SHA-256 checksum

Everyone must train on the same file. Compute its checksum and compare it with the value in
`dataset.sha256` of `ml/artifacts/manifest.json` (the first person who trains records it there).

```bash
# Windows (PowerShell)
Get-FileHash ml/data/raw/Loan_default.csv -Algorithm SHA256

# Linux / macOS
sha256sum ml/data/raw/Loan_default.csv

# Any platform, with the project venv
python -c "import hashlib, pathlib; print(hashlib.sha256(pathlib.Path('ml/data/raw/Loan_default.csv').read_bytes()).hexdigest())"
```

If the checksum differs, do not train: download the file again and tell the team.

## Test fixture

`tests/fixtures/loan_default_sample.csv` has 60 **synthetic** rows with the same 18 columns
(about 15 % `Default = 1`). It is not a sample of the real dataset; it only lets the tests run
without downloading anything.
