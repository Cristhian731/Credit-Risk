"""Train the three candidate models, pick the champion and save the artifacts.

Usage from the project root:

    python -m ml.train [--data ml/data/raw/Loan_default.csv] [--out ml/artifacts]

Protocol (also written to experiments.json):

* The hyperparameter search and the champion selection use ONLY the train
  split, with 5-fold stratified cross-validation.
* The held-out test split is evaluated exactly once per model, after its
  hyperparameters are fixed. Test metrics are reported, never used to tune
  a model, pick the champion or judge a different configuration.

Output layout (see docs/ML_PHASE.md and ml.schemas):

    <out>/manifest.json         champion, dataset SHA-256 and success criteria
    <out>/data_report.json      data quality before/after (statistics only)
    <out>/experiments.json      every hyperparameter run of every model
    <out>/overfitting.json      train vs. CV vs. test ROC AUC
    <out>/subgroups.json        test metrics by age range and employment type
    <out>/<model name>/model.joblib
    <out>/<model name>/metrics.json
"""
import argparse
import json
import math
import os
import time
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.metrics import make_scorer, precision_score, f1_score, recall_score, roc_auc_score
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold

from ml import dataset
from ml.dataset import DEFAULT_DATA_PATH
from ml.evaluate import evaluate, evaluate_subgroups
from ml.features import (
    ARTIFACTS_DIR,
    DEFAULT_FEATURE_SET,
    FEATURE_SETS,
    MANIFEST_FILENAME,
    METRICS_FILENAME,
    MODEL_FILENAME,
)
from ml.pipelines import RANDOM_STATE, SEARCH_SPACES, build_pipeline
from ml.schemas import (
    CV_METRICS,
    DATA_REPORT_FILENAME,
    DISPLAY_NAMES,
    EXPERIMENTS_FILENAME,
    MAX_ARTIFACTS_BYTES,
    MODEL_NAMES,
    OVERFITTING_FILENAME,
    SUBGROUPS_FILENAME,
    artifacts_size,
    validate_artifacts,
)

CV_FOLDS = 5
# Models whose mean CV ROC AUC is less than this below the best one are tied;
# among them the higher mean CV recall (class 1) wins.
CHAMPION_AUC_MARGIN = 0.01
# Hyperparameter candidates sampled per model (capped by the size of the space).
SEARCH_ITERATIONS = 8

# Success criteria checked on the champion and recorded in the manifest.
MIN_CV_ROC_AUC = 0.70
MIN_CV_RECALL = 0.60
MAX_CV_TEST_AUC_GAP = 0.02
# train ROC AUC minus mean CV ROC AUC above this is flagged as overfitting.
OVERFIT_GAP = 0.05

SELECTION_RULE = (
    "Highest mean ROC AUC in 5-fold stratified cross-validation on the train split; "
    "models less than 0.01 below the best are tied and the highest mean CV recall "
    "(class 1) wins. The 20% test split is only reported."
)

SCORING = {
    "roc_auc": "roc_auc",
    "recall": make_scorer(recall_score, zero_division=0),
    "precision": make_scorer(precision_score, zero_division=0),
    "f1": make_scorer(f1_score, zero_division=0),
}


def select_champion(metrics_by_model):
    """Pick the official model using cross-validation results only.

    Rule: highest mean CV ROC AUC (5-fold stratified, train split). Every
    model whose mean CV ROC AUC is less than ``CHAMPION_AUC_MARGIN`` below
    the best one stays in the race, and among them the highest mean CV
    recall of class 1 wins. A remaining exact tie goes to the first model in
    ``ml.schemas.MODEL_NAMES`` order. Test metrics are never used here.

    Args:
        metrics_by_model: ``{model name: metrics.json content}``.

    Returns:
        The champion's model name.

    Raises:
        ValueError: If ``metrics_by_model`` is empty.
    """
    if not metrics_by_model:
        raise ValueError("select_champion needs at least one model")

    order = {name: index for index, name in enumerate(MODEL_NAMES)}
    names = sorted(metrics_by_model, key=lambda name: order.get(name, len(order)))

    def cv_mean(name, metric):
        return metrics_by_model[name]["cv"][metric][0]

    best_auc = max(cv_mean(name, "roc_auc") for name in names)
    tied = [name for name in names if best_auc - cv_mean(name, "roc_auc") < CHAMPION_AUC_MARGIN]
    best_recall = max(cv_mean(name, "recall") for name in tied)
    return next(name for name in tied if cv_mean(name, "recall") == best_recall)


def _json_value(value):
    return isinstance(value, (str, int, float, bool)) or value is None


def _classifier_params(pipeline):
    """Hyperparameters of the classifier that can be written to JSON."""
    params = pipeline.named_steps["classifier"].get_params()
    return {
        key: value for key, value in sorted(params.items())
        if _json_value(value) and not (isinstance(value, float) and not math.isfinite(value))
    }


def _feature_importance(pipeline, feature_set):
    """Importance per original column (one-hot columns are added up), summing to 1."""
    config = FEATURE_SETS[feature_set]
    classifier = pipeline.named_steps["classifier"]
    if hasattr(classifier, "feature_importances_"):
        raw = np.asarray(classifier.feature_importances_, dtype=float)
    else:
        raw = np.abs(np.asarray(classifier.coef_, dtype=float)).ravel()

    names = pipeline.named_steps["preprocessing"].get_feature_names_out()
    totals = {column: 0.0 for column in config["columns"]}
    for name, value in zip(names, raw):
        name = name.split("__", 1)[-1]
        column = next(
            (c for c in config["categorical"] if name == c or name.startswith(c + "_")),
            name,
        )
        totals[column] += float(value)

    total = sum(totals.values()) or 1.0
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    return [{"feature": column, "importance": round(value / total, 6)} for column, value in ranked]


def _search(name, X_train, y_train, scale_pos_weight, n_iter, n_jobs):
    """Hyperparameter search for one model with CV on the train split only."""
    space = SEARCH_SPACES[name]
    size = math.prod(len(values) for values in space.values())
    candidates = min(n_iter, size)
    search = RandomizedSearchCV(
        build_pipeline(name, scale_pos_weight=scale_pos_weight),
        space,
        n_iter=candidates,
        scoring=SCORING,
        refit="roc_auc",
        cv=StratifiedKFold(CV_FOLDS, shuffle=True, random_state=RANDOM_STATE),
        n_jobs=n_jobs,
        random_state=RANDOM_STATE,
    )
    started = time.perf_counter()
    search.fit(X_train, y_train)
    seconds = time.perf_counter() - started

    results = search.cv_results_
    runs = []
    for index, params in enumerate(results["params"]):
        runs.append({
            "run": index + 1,
            "params": {key.split("__", 1)[-1]: value for key, value in params.items()},
            "cv": {
                metric: [
                    round(float(results[f"mean_test_{metric}"][index]), 6),
                    round(float(results[f"std_test_{metric}"][index]), 6),
                ]
                for metric in CV_METRICS
            },
            "fit_seconds": round(float(results["mean_fit_time"][index]), 3),
            "selected": bool(index == search.best_index_),
        })
    experiment = {
        "search_space": {key.split("__", 1)[-1]: list(values) for key, values in space.items()},
        "n_candidates": candidates,
        "search_seconds": round(seconds, 1),
        "runs": runs,
    }
    return search.best_estimator_, runs[search.best_index_]["cv"], experiment


def _success_criteria(champion, metrics):
    cv_auc = metrics["cv"]["roc_auc"][0]
    cv_recall = metrics["cv"]["recall"][0]
    gap = abs(cv_auc - metrics["test"]["roc_auc"])
    results = [
        {"criterion": f"Mean CV ROC AUC >= {MIN_CV_ROC_AUC}", "threshold": MIN_CV_ROC_AUC,
         "value": round(cv_auc, 4), "passed": bool(cv_auc >= MIN_CV_ROC_AUC)},
        {"criterion": f"Mean CV recall of class 1 >= {MIN_CV_RECALL}", "threshold": MIN_CV_RECALL,
         "value": round(cv_recall, 4), "passed": bool(cv_recall >= MIN_CV_RECALL)},
        {"criterion": f"|CV ROC AUC - test ROC AUC| <= {MAX_CV_TEST_AUC_GAP}", "threshold": MAX_CV_TEST_AUC_GAP,
         "value": round(gap, 4), "passed": bool(gap <= MAX_CV_TEST_AUC_GAP)},
    ]
    return {"champion": champion, "all_passed": all(item["passed"] for item in results), "results": results}


def build_findings(subgroups, champion, feature_importance):
    """Plain-language findings about group differences of the champion (for the Phase 4 page).

    Computed only from the subgroup statistics of the test split and the
    champion's feature importance; reported, never used to tune or select.

    Args:
        subgroups: ``{model: {"age_range": {...}, "employment_type": {...}}}``.
        champion: Name of the champion model.
        feature_importance: The champion's ``feature_importance`` list.
    """
    groups = subgroups[champion]
    ages = groups["age_range"]
    youngest, oldest = ages[min(ages)], ages[max(ages)]
    employment_groups = groups["employment_type"].values()
    complete = (
        all("recall" in g and "roc_auc" in g for g in list(ages.values()) + list(employment_groups))
        and youngest["default_rate"] > 0
    )
    if not complete:
        # Tiny datasets (such as the test fixture) leave some groups without metrics.
        return [
            {
                "id": dimension_id, "dimension": dimension, "model": champion, "severity": "low",
                "title": "Not enough rows per group to compare",
                "summary": "Some groups are too small (or have a single class) to report recall and ROC AUC.",
                "evidence": {}, "recommendation": "Train with the full dataset to see this finding.",
            }
            for dimension_id, dimension in (("age_bias", "age_range"), ("employment_type_gap", "employment_type"))
        ]
    age_importance = next((item["importance"] for item in feature_importance if item["feature"] == "Age"), 0.0)

    findings = [{
        "id": "age_bias",
        "dimension": "age_range",
        "model": champion,
        "severity": "high",
        "title": "The champion flags young applicants far more often than older ones",
        "summary": (
            f"Applicants aged {min(ages)} are predicted as defaults {youngest['predicted_default_rate']:.0%} of the time "
            f"although {youngest['default_rate']:.0%} actually default (about "
            f"{youngest['predicted_default_rate'] / youngest['default_rate']:.1f} times the real rate). "
            f"At ages {max(ages)} only {oldest['predicted_default_rate']:.0%} are flagged "
            f"({oldest['default_rate']:.0%} actually default). Recall of class 1 goes from "
            f"{youngest['recall']:.0%} for the youngest to {oldest['recall']:.0%} for the oldest: young defaulters "
            f"are caught almost always at the price of many false alarms, while older defaulters are mostly missed. "
            f"Age is the most important input ({age_importance:.0%} of the importance), and part of the gap mirrors "
            f"a real difference in default rates. ROC AUC is similar across ages "
            f"({min(g['roc_auc'] for g in ages.values() if 'roc_auc' in g):.2f} to "
            f"{max(g['roc_auc'] for g in ages.values() if 'roc_auc' in g):.2f}), so the ranking quality is "
            f"comparable and the gap mostly comes from applying one 0.5 threshold with balanced class weights to groups with different base rates."
        ),
        "evidence": {
            "predicted_default_rate": {label: g["predicted_default_rate"] for label, g in ages.items()},
            "default_rate": {label: g["default_rate"] for label, g in ages.items()},
            "recall": {label: g["recall"] for label, g in ages.items() if "recall" in g},
        },
        "recommendation": (
            "Treat age as a sensitive attribute: review the threshold per group, test the model without Age, "
            "and keep a human review for rejected young applicants before using it in real decisions."
        ),
    }]

    employment = groups["employment_type"]
    low = min(employment, key=lambda label: employment[label]["predicted_default_rate"])
    high = max(employment, key=lambda label: employment[label]["predicted_default_rate"])
    findings.append({
        "id": "employment_type_gap",
        "dimension": "employment_type",
        "model": champion,
        "severity": "moderate",
        "title": "Flag rates differ by employment type, in line with the real default rates",
        "summary": (
            f"{high} applicants are flagged {employment[high]['predicted_default_rate']:.0%} of the time "
            f"({employment[high]['default_rate']:.1%} actually default) against "
            f"{employment[low]['predicted_default_rate']:.0%} for {low} "
            f"({employment[low]['default_rate']:.1%} actually default). ROC AUC stays between "
            f"{min(g['roc_auc'] for g in employment.values()):.2f} and "
            f"{max(g['roc_auc'] for g in employment.values()):.2f}."
        ),
        "evidence": {
            "predicted_default_rate": {label: g["predicted_default_rate"] for label, g in employment.items()},
            "default_rate": {label: g["default_rate"] for label, g in employment.items()},
            "recall": {label: g["recall"] for label, g in employment.items() if "recall" in g},
        },
        "recommendation": "Monitor these rates in production (Phase 6) and recheck them after each retraining.",
    })
    return findings


def _write_json(path, document):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(document, fh, indent=2, ensure_ascii=False, allow_nan=False)
        fh.write("\n")


def run(data_path=DEFAULT_DATA_PATH, out_dir=ARTIFACTS_DIR, n_iter=SEARCH_ITERATIONS, n_jobs=-1):
    """Load, split, cross-validate, fit, evaluate and save every model.

    Writes the layout described in the module docstring, with the dataset
    SHA-256 in ``manifest["dataset"]``, and returns the manifest dict. The
    result must pass ``ml.schemas.validate_artifacts(out_dir)``.

    The search and the champion selection only see the train split; the test
    split is evaluated once per model afterwards (see the module docstring).
    """
    started = time.perf_counter()
    now = datetime.now(timezone.utc)
    trained_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    version = f"{now:%Y-%m-%d}.1"
    feature_set = DEFAULT_FEATURE_SET

    raw = dataset.load(data_path)
    cleaned = dataset.clean(raw)
    X_train, X_test, y_train, y_test = dataset.split(cleaned)
    data_report = dataset.build_data_report(raw, cleaned, y_train, y_test)

    scale_pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())

    os.makedirs(out_dir, exist_ok=True)
    metrics_by_model, experiments, overfitting, subgroups = {}, {}, {}, {}
    for name in MODEL_NAMES:
        print(f"[{name}] searching hyperparameters (train split, {CV_FOLDS}-fold CV)...", flush=True)
        model, cv, experiment = _search(name, X_train, y_train, scale_pos_weight, n_iter, n_jobs)
        experiments[name] = experiment

        # The test split is evaluated here, once, with the hyperparameters already fixed.
        evaluation = evaluate(model, X_test, y_test)
        train_auc = float(roc_auc_score(y_train, model.predict_proba(X_train)[:, 1]))
        cv_auc, test_auc = cv["roc_auc"][0], evaluation["test"]["roc_auc"]

        metrics_by_model[name] = {
            "model": name,
            "display_name": DISPLAY_NAMES[name],
            "model_version": version,
            "cv": cv,
            **evaluation,
            "feature_importance": _feature_importance(model, feature_set),
            "params": _classifier_params(model),
        }
        overfitting[name] = {
            "train_roc_auc": round(train_auc, 4),
            "cv_roc_auc": round(cv_auc, 4),
            "test_roc_auc": round(test_auc, 4),
            "train_minus_cv": round(train_auc - cv_auc, 4),
            "cv_minus_test": round(cv_auc - test_auc, 4),
            "overfit": bool(train_auc - cv_auc > OVERFIT_GAP),
        }
        subgroups[name] = evaluate_subgroups(model, X_test, y_test)

        model_dir = os.path.join(out_dir, name)
        os.makedirs(model_dir, exist_ok=True)
        joblib.dump(model, os.path.join(model_dir, MODEL_FILENAME), compress=3)
        _write_json(os.path.join(model_dir, METRICS_FILENAME), metrics_by_model[name])
        print(f"[{name}] CV AUC {cv_auc:.4f}  test AUC {test_auc:.4f}  "
              f"search {experiment['search_seconds']}s", flush=True)

    champion = select_champion(metrics_by_model)
    total_seconds = round(time.perf_counter() - started, 1)

    manifest = {
        "version": version,
        "trained_at": trained_at,
        "dataset": {
            "name": data_report["dataset"]["name"],
            "sha256": raw.attrs["sha256"],
            "expected_sha256": dataset.EXPECTED_SHA256,
            "sha256_matches_expected": raw.attrs["sha256"] == dataset.EXPECTED_SHA256,
            "rows": int(len(raw)),
        },
        "feature_set": feature_set,
        "selection_rule": SELECTION_RULE,
        "champion": champion,
        "models": list(MODEL_NAMES),
        "success_criteria": _success_criteria(champion, metrics_by_model[champion]),
    }

    _write_json(os.path.join(out_dir, MANIFEST_FILENAME), manifest)
    _write_json(os.path.join(out_dir, DATA_REPORT_FILENAME), data_report)
    _write_json(os.path.join(out_dir, EXPERIMENTS_FILENAME), {
        "version": version,
        "trained_at": trained_at,
        "protocol": {
            "selection_data": f"Train split only ({len(y_train)} rows), {CV_FOLDS}-fold stratified cross-validation.",
            "test_usage": f"The test split ({len(y_test)} rows) is evaluated exactly once per model, after its "
                          "hyperparameters are fixed. It is never used to tune a model or to pick the champion.",
            "scoring": "roc_auc (refit and selection of the best run); recall, precision and f1 are class 1 at threshold 0.5.",
            "cv_folds": CV_FOLDS,
            "random_state": RANDOM_STATE,
            "search": f"RandomizedSearchCV, up to {n_iter} candidates per model.",
        },
        "total_seconds": total_seconds,
        "models": experiments,
    })
    _write_json(os.path.join(out_dir, OVERFITTING_FILENAME), {
        "version": version,
        "threshold": OVERFIT_GAP,
        "models": overfitting,
    })
    _write_json(os.path.join(out_dir, SUBGROUPS_FILENAME), {
        "version": version,
        "split": {"set": "test", "rows": int(len(y_test)),
                  "note": "Reported only; never used to tune or select a model."},
        "findings": build_findings(subgroups, champion, metrics_by_model[champion]["feature_importance"]),
        "models": subgroups,
    })

    errors = validate_artifacts(out_dir, require_models=True)
    if errors:
        raise RuntimeError("Invalid artifacts: " + "; ".join(errors))
    size = artifacts_size(out_dir)
    if size >= MAX_ARTIFACTS_BYTES:
        raise RuntimeError(f"Artifacts take {size} bytes; the limit is {MAX_ARTIFACTS_BYTES}")
    print(f"Champion: {champion}. Total {total_seconds}s. Artifacts {size / 1024 / 1024:.1f} MB.", flush=True)
    return manifest


def parse_args(argv=None):
    """Parse the command line of ``python -m ml.train``."""
    parser = argparse.ArgumentParser(
        prog="python -m ml.train",
        description="Train the candidate credit risk models and save the artifacts.",
    )
    parser.add_argument("--data", default=DEFAULT_DATA_PATH, help="path to Loan_default.csv")
    parser.add_argument("--out", default=ARTIFACTS_DIR, help="artifacts directory")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    run(args.data, args.out)


if __name__ == "__main__":
    main()
