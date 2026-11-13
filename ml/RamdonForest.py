import json
import sys

import joblib
import numpy as np
import pandas as pd
from pathlib import Path
OUT_DIR = Path(__file__).parent / "artifacts"
OUT_DIR.mkdir(exist_ok=True)
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_curve,
    precision_recall_fscore_support,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import RandomizedSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "Loan_default.csv"
TARGET = "Default"            # 1 = defaults, 0 = repays (change it if your CSV uses another name)
TUNE_HYPERPARAMETERS = False  # set to True to run a randomized search (slower)
SEED = 42


df = pd.read_csv(CSV_PATH)
print("Shape:", df.shape)
print(df.head(), "\n")

# Drop identifier columns (LoanID, ID, ...): they carry no predictive signal
id_cols = [c for c in df.columns if c.lower() in ("loanid", "loan_id", "id")]
df = df.drop(columns=id_cols).drop_duplicates().dropna(subset=[TARGET])

print("Target distribution:")
print(df[TARGET].value_counts(normalize=True).round(3), "\n")

X = df.drop(columns=[TARGET])
y = df[TARGET].astype(int)

num_cols = X.select_dtypes(include="number").columns.tolist()
cat_cols = X.select_dtypes(exclude="number").columns.tolist()
print("Numeric features:", num_cols)
print("Categorical features:", cat_cols, "\n")


X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=SEED
)


preprocessor = ColumnTransformer(
    transformers=[
        ("num", SimpleImputer(strategy="median"), num_cols),
        (
            "cat",
            Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("onehot", OneHotEncoder(handle_unknown="ignore")),
                ]
            ),
            cat_cols,
        ),
    ]
)

model = Pipeline(
    [
        ("prep", preprocessor),
        (
            "rf",
            RandomForestClassifier(
                n_estimators=300,
                max_depth=None,
                min_samples_leaf=5,
                class_weight="balanced_subsample",  # compensates for few defaulters
                n_jobs=-1,
                random_state=SEED,
            ),
        ),
    ]
)

if TUNE_HYPERPARAMETERS:
    search = RandomizedSearchCV(
        model,
        {
            "rf__n_estimators": [200, 300, 500],
            "rf__max_depth": [None, 10, 20, 30],
            "rf__min_samples_leaf": [1, 3, 5, 10],
            "rf__max_features": ["sqrt", "log2", 0.5],
        },
        n_iter=15,
        scoring="roc_auc",
        cv=3,
        n_jobs=-1,
        random_state=SEED,
        verbose=1,
    )
    search.fit(X_train, y_train)
    print("Best parameters:", search.best_params_)
    model = search.best_estimator_
else:
    model.fit(X_train, y_train)


y_prob = model.predict_proba(X_test)[:, 1]  
precision, recall, thresholds = precision_recall_curve(y_test, y_prob)
f1_curve = 2 * precision * recall / (precision + recall + 1e-9)
best_threshold = float(thresholds[f1_curve[:-1].argmax()])


def evaluate(threshold):
    pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, pred).ravel()
    p, r, f, _ = precision_recall_fscore_support(
        y_test, pred, average="binary", zero_division=0
    )
    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y_test, pred)),
        "precision": float(p),
        "recall": float(r),
        "f1": float(f),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


auc = float(roc_auc_score(y_test, y_prob))
metrics = {"default": evaluate(0.5), "suggested": evaluate(best_threshold)}

for name, m in metrics.items():
    print(f"\n=== Threshold {m['threshold']:.3f} ({name}) ===")
    print({k: round(v, 4) for k, v in m.items() if isinstance(v, float)})
    print("Confusion matrix:", m["confusion_matrix"])
print("\nAUC-ROC:", round(auc, 4))


names = model.named_steps["prep"].get_feature_names_out()
importances = (
    pd.Series(model.named_steps["rf"].feature_importances_, index=names)
    .sort_values(ascending=False)
    .head(15)
)
print("\nTop 10 features:")
print(importances.head(10).round(4))


joblib.dump(
    {"model": model, "threshold": best_threshold, "columns": X.columns.tolist()},
    "credit_risk_model.joblib",
)


fpr, tpr, _ = roc_curve(y_test, y_prob)
idx = np.linspace(0, len(fpr) - 1, min(200, len(fpr))).astype(int)  # downsample

rf = model.named_steps["rf"]
results = {
    "dataset": {
        "file": CSV_PATH,
        "rows": int(len(df)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "features": int(X.shape[1]),
        "default_rate": float(y.mean()),
    },
    "model": {
        "name": "Random Forest",
        "n_estimators": int(rf.n_estimators),
        "max_depth": rf.max_depth,
        "min_samples_leaf": rf.min_samples_leaf,
        "class_weight": str(rf.class_weight),
    },
    "auc": auc,
    "metrics": metrics,
    "roc": {"fpr": fpr[idx].round(4).tolist(), "tpr": tpr[idx].round(4).tolist()},
    "importances": [{"feature": k, "value": float(v)} for k, v in importances.items()],
}

with open("training_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
with open("training_results.js", "w") as f:  # lets the HTML load it when opened from disk
    f.write("window.TRAINING_RESULTS = " + json.dumps(results, default=str) + ";")

print("\nSaved: credit_risk_model.joblib, training_results.json, training_results.js")


package = joblib.load("credit_risk_model.joblib")
client = X_test.iloc[[0]]  # in the web app, build this one-row DataFrame from the form
prob = package["model"].predict_proba(client)[0, 1]
verdict = "NOT viable" if prob >= package["threshold"] else "Viable"
print(f"Default probability: {prob:.1%} -> Loan is {verdict}")