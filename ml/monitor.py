"""Monitoring of the champion: PSI per feature of a batch against the train distribution.

Usage from the project root:

    python -m ml.monitor --build-reference          # statistics of the train split (needs the dataset)
    python -m ml.monitor --simulated                # SIMULATED batch with an intentional drift
    python -m ml.monitor --log logs/predictions.jsonl   # a real batch: the prediction log of the app

Output (next to manifest.json):

    reference_distribution.json   bins and fractions of every model feature in the train split
                                  (only statistics, no rows), written by --build-reference
    monitoring_report.json        PSI per feature, label rates and status of a batch

PSI (population stability index) compares the share of a batch in each bin with the share of the
train split in that bin: ``sum((actual - expected) * ln(actual / expected))``. Below 0.1 the
feature is stable, from 0.1 to 0.25 it must be watched and above 0.25 it is an alert. The test
split is never used. The SIMULATED batch is created with a fixed seed from the reference
distribution and carries an intentional drift, so the alert can be seen; it is labeled SIMULATED
in the report and in the application.
"""
import argparse
import json
import os
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from ml import dataset
from ml.features import (
    ARTIFACTS_DIR,
    DEFAULT_FEATURE_SET,
    FEATURE_SETS,
    MANIFEST_FILENAME,
    MODEL_FILENAME,
)
from ml.schemas import (
    MONITORING_REPORT_FILENAME,
    PSI_ALERT,
    PSI_STABLE,
    REFERENCE_DISTRIBUTION_FILENAME,
    RISK_LABELS,
    load_json,
    psi_status,
    validate_monitoring_report,
    validate_reference_distribution,
)

BINS = 10
EPSILON = 1e-4  # fractions are floored at this value so that an empty bin does not break the logarithm
# Risk thresholds of the application (config.py: CREDIT_APPROVED_MAX_RISK / CREDIT_MEDIUM_MAX_RISK).
APPROVED_MAX = 0.33
MEDIUM_MAX = 0.66

SIMULATED_ROWS = 2000
# A PSI computed from fewer rows than this is mostly sampling noise (10 bins per feature).
MIN_RELIABLE_ROWS = 500
SIMULATED_SEED = 42
# The drift put on purpose in the SIMULATED batch: feature -> (kind, amount).
SIMULATED_DRIFT = {
    "CreditScore": ("shift", -80),
    "LoanAmount": ("scale", 1.15),
}

NOTE = "Statistics of the train split (bins and fractions). It has no rows of the dataset."


def label_for(risk):
    """Risk label of a default probability, with the thresholds of the application."""
    if risk < APPROVED_MAX:
        return RISK_LABELS[0]
    return RISK_LABELS[1] if risk < MEDIUM_MAX else RISK_LABELS[2]


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path, document):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(document, fh, indent=2, ensure_ascii=False, allow_nan=False)
        fh.write("\n")


def _round(value, digits=6):
    return round(float(value), digits)


# ---------------------------------------------------------------------------
# PSI
# ---------------------------------------------------------------------------

def psi(expected, actual):
    """Population stability index between two lists of fractions (same bins)."""
    e = np.maximum(np.asarray(expected, dtype=float), EPSILON)
    a = np.maximum(np.asarray(actual, dtype=float), EPSILON)
    return float(np.sum((a - e) * np.log(a / e)))


def bin_fractions(values, cuts):
    """Share of ``values`` in each bin: bin i holds the values <= cuts[i], the last one the rest."""
    values = np.asarray(values, dtype=float)
    index = np.searchsorted(np.asarray(cuts, dtype=float), values, side="left")
    return (np.bincount(index, minlength=len(cuts) + 1) / len(values)).tolist()


def batch_psi(batch, reference):
    """PSI of every model feature of ``batch`` (a DataFrame) against the reference distribution."""
    result = {}
    for name, item in reference["numeric"].items():
        result[name] = psi(item["fractions"], bin_fractions(batch[name], item["cuts"]))
    for name, expected in reference["categorical"].items():
        categories = list(expected) + [c for c in sorted(set(batch[name])) if c not in expected]
        counts = batch[name].value_counts(normalize=True)
        result[name] = psi(
            [expected.get(c, 0.0) for c in categories], [float(counts.get(c, 0.0)) for c in categories]
        )
    return result


# ---------------------------------------------------------------------------
# Reference distribution (train split)
# ---------------------------------------------------------------------------

def build_reference(data_path=dataset.DEFAULT_DATA_PATH, artifacts_dir=ARTIFACTS_DIR):
    """Write reference_distribution.json from the train split (never the test split) and return it."""
    manifest = load_json(os.path.join(artifacts_dir, MANIFEST_FILENAME))
    feature_set = manifest["feature_set"]
    config = FEATURE_SETS[feature_set]
    columns = list(config["columns"])

    raw = dataset.load(data_path)
    X_train, _X_test, _y_train, _y_test = dataset.split(dataset.clean(raw))

    numeric = {}
    for name in columns:
        if name in config["categorical"]:
            continue
        values = X_train[name].to_numpy(dtype=float)
        cuts = np.unique(np.quantile(values, np.linspace(0, 1, BINS + 1)[1:-1]))
        cuts = cuts[cuts < values.max()]  # no empty last bin
        numeric[name] = {
            "cuts": [_round(c) for c in cuts],
            "fractions": [_round(f) for f in bin_fractions(values, cuts)],
            "min": _round(values.min()),
            "max": _round(values.max()),
            "mean": _round(values.mean()),
            "integer": bool(np.all(values == np.round(values))),
        }
    categorical = {
        name: {str(k): _round(v) for k, v in X_train[name].value_counts(normalize=True).items()}
        for name in config["categorical"]
    }

    champion = manifest["champion"]
    model = joblib.load(os.path.join(artifacts_dir, champion, MODEL_FILENAME))
    risk = model.predict_proba(X_train[columns])[:, 1]
    labels = pd.Series([label_for(r) for r in risk])
    reference = {
        "version": manifest["version"],
        "feature_set": feature_set,
        "dataset": {"sha256": raw.attrs["sha256"], "train_rows": int(len(X_train))},
        "bins": BINS,
        "numeric": numeric,
        "categorical": categorical,
        "labels": {
            "model": champion,
            "thresholds": {"approved_max": APPROVED_MAX, "medium_max": MEDIUM_MAX},
            "rates": {label: _round((labels == label).mean()) for label in RISK_LABELS},
            "mean_risk": _round(risk.mean()),
        },
        "note": NOTE,
    }
    errors = validate_reference_distribution(reference)
    if errors:
        raise RuntimeError("Invalid reference distribution: " + "; ".join(errors))
    _write_json(os.path.join(artifacts_dir, REFERENCE_DISTRIBUTION_FILENAME), reference)
    return reference


# ---------------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------------

def simulated_batch(reference, rows=SIMULATED_ROWS, seed=SIMULATED_SEED, drift=None):
    """A SIMULATED batch: applicants resampled from the train distribution plus an intentional drift."""
    drift = SIMULATED_DRIFT if drift is None else drift
    rng = np.random.default_rng(seed)
    data = {}
    for name, item in reference["numeric"].items():
        edges = [item["min"]] + list(item["cuts"]) + [item["max"]]
        chosen = rng.choice(len(item["fractions"]), size=rows, p=np.asarray(item["fractions"]) / sum(item["fractions"]))
        if item["integer"]:
            # Whole numbers inside the bin: (previous cut, cut], and the first bin starts at the minimum.
            low = np.array([np.ceil(edges[0])] + [np.floor(c) + 1 for c in edges[1:-1]])
            high = np.floor(np.array(edges[1:]))
            data[name] = rng.integers(np.take(low, chosen), np.take(high, chosen) + 1).astype(float)
        else:
            data[name] = rng.uniform(np.take(edges[:-1], chosen), np.take(edges[1:], chosen))
    for name, fractions in reference["categorical"].items():
        categories = list(fractions)
        data[name] = rng.choice(categories, size=rows, p=np.asarray(list(fractions.values())) / sum(fractions.values()))
    for name, (kind, amount) in drift.items():
        data[name] = data[name] + amount if kind == "shift" else data[name] * amount
        if name == "CreditScore":
            data[name] = np.clip(data[name], 300, 850)
    return pd.DataFrame(data)[list(reference["numeric"]) + list(reference["categorical"])]


def batch_from_log(path):
    """Read a prediction log (JSON lines): the model inputs, the risk and the label of every prediction."""
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    if not records:
        raise ValueError(f"The prediction log {path} has no predictions.")
    batch = pd.DataFrame([record["inputs"] for record in records])
    risk = np.array([record["probability"] for record in records], dtype=float)
    period = {"from": min(r["timestamp"] for r in records), "to": max(r["timestamp"] for r in records)}
    return batch, risk, period


def _rates(labels):
    labels = pd.Series(list(labels))
    return {label: _round((labels == label).mean()) for label in RISK_LABELS}


def build_report(batch, risk, reference, manifest, source, seed=None, period=None, drift=None):
    """The content of monitoring_report.json for a batch (see ml.schemas.validate_monitoring_report)."""
    values = batch_psi(batch, reference)
    psi_report = {name: {"value": _round(v), "status": psi_status(_round(v))} for name, v in values.items()}
    statuses = [item["status"] for item in psi_report.values()]
    overall = "alert" if "alert" in statuses else "watch" if "watch" in statuses else "stable"
    in_alert = [n for n, item in psi_report.items() if item["status"] == "alert"]
    to_watch = [n for n, item in psi_report.items() if item["status"] == "watch"]

    batch_rates = _rates(label_for(r) for r in risk)
    reference_rates = reference["labels"]["rates"]
    simulated = source == "SIMULATED"
    recommendation = {
        "stable": "No action: every feature is stable. Keep the scheduled review.",
        "watch": "Watch: review the features listed in features_to_watch at the next scheduled check.",
        "alert": "Alert: investigate the features in alert, check the data source and decide whether to retrain.",
    }[overall]
    if not simulated and len(batch) < MIN_RELIABLE_ROWS:
        recommendation += (
            f" Only {len(batch)} predictions in the log (fewer than {MIN_RELIABLE_ROWS}): the PSI values are"
            " dominated by sampling noise and do not show drift. Wait for a larger batch."
        )
    if simulated:
        recommendation += " This batch is SIMULATED with an intentional drift: it only demonstrates the procedure."
    return {
        "generated_at": _now(),
        "source": source,
        "simulated": simulated,
        "model": reference["labels"]["model"],
        "artifacts_version": manifest["version"],
        "reference": {"rows": reference["dataset"]["train_rows"], "dataset_sha256": reference["dataset"]["sha256"]},
        "batch": {
            "rows": int(len(batch)),
            "seed": seed,
            "period": period,
            "drift_injected": [
                {"feature": name, "kind": kind, "amount": amount} for name, (kind, amount) in (drift or {}).items()
            ] if simulated else [],
        },
        "thresholds": {"stable_below": PSI_STABLE, "alert_above": PSI_ALERT},
        "psi": psi_report,
        "overall_status": overall,
        "features_in_alert": in_alert,
        "features_to_watch": to_watch,
        "labels": {
            "reference": reference_rates,
            "batch": batch_rates,
            "difference": {label: _round(batch_rates[label] - reference_rates[label]) for label in RISK_LABELS},
        },
        "risk": {"reference_mean": reference["labels"]["mean_risk"], "batch_mean": _round(np.mean(risk))},
        "recommendation": recommendation,
    }


def run(log_path=None, simulated=False, artifacts_dir=ARTIFACTS_DIR, rows=SIMULATED_ROWS, seed=SIMULATED_SEED):
    """Compute the monitoring report of a batch and write monitoring_report.json."""
    reference = load_json(os.path.join(artifacts_dir, REFERENCE_DISTRIBUTION_FILENAME))
    manifest = load_json(os.path.join(artifacts_dir, MANIFEST_FILENAME))
    if simulated:
        batch = simulated_batch(reference, rows, seed)
        model = joblib.load(os.path.join(artifacts_dir, reference["labels"]["model"], MODEL_FILENAME))
        risk = model.predict_proba(batch)[:, 1]
        report = build_report(batch, risk, reference, manifest, "SIMULATED", seed=seed, drift=SIMULATED_DRIFT)
    else:
        batch, risk, period = batch_from_log(log_path)
        report = build_report(batch, risk, reference, manifest, "PREDICTION_LOG", period=period)
    errors = validate_monitoring_report(report)
    if errors:
        raise RuntimeError("Invalid monitoring report: " + "; ".join(errors))
    _write_json(os.path.join(artifacts_dir, MONITORING_REPORT_FILENAME), report)
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m ml.monitor",
        description="PSI of a batch of predictions against the train distribution.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--build-reference", action="store_true", help="write reference_distribution.json from the dataset")
    source.add_argument("--simulated", action="store_true", help="use a SIMULATED batch with an intentional drift")
    source.add_argument("--log", help="path of the prediction log (JSON lines) to analyse")
    parser.add_argument("--data", default=dataset.DEFAULT_DATA_PATH, help="path to Loan_default.csv (--build-reference)")
    parser.add_argument("--out", default=ARTIFACTS_DIR, help="artifacts directory")
    parser.add_argument("--rows", type=int, default=SIMULATED_ROWS, help="rows of the SIMULATED batch")
    parser.add_argument("--seed", type=int, default=SIMULATED_SEED, help="seed of the SIMULATED batch")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.build_reference:
        reference = build_reference(args.data, args.out)
        print(f"Reference distribution written ({reference['dataset']['train_rows']} train rows, no rows stored).")
        return
    report = run(args.log, args.simulated, args.out, args.rows, args.seed)
    print(f"{report['source']} batch of {report['batch']['rows']} rows: {report['overall_status']}")
    for name, item in report["psi"].items():
        print(f"  {name:<16} PSI {item['value']:.4f}  {item['status']}")


if __name__ == "__main__":
    main()
