"""Monitoring: PSI report (ml.monitor), prediction log, retention and the demo account password."""
import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

import config
from app.credit.prediction_log import RECORD_KEYS, PredictionLog
from app.credit.services import ModelRegistry
from app.models import User
from app.services import repository
from ml import monitor
from ml.features import ARTIFACTS_DIR, EXAMPLE_ARTIFACTS_DIR, FEATURE_SETS
from ml.schemas import (
    MONITORING_REPORT_FILENAME,
    PSI_ALERT,
    PSI_STABLE,
    REFERENCE_DISTRIBUTION_FILENAME,
    load_json,
    psi_status,
    validate_artifacts,
    validate_monitoring_report,
    validate_reference_distribution,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_FEATURES = list(FEATURE_SETS["v2-loan-default"]["columns"])
FORM = {
    "client_full_name": "Maria Lopez", "client_document": "100200300",
    "age": "35", "monthly_income": "4000", "employment_status": "employed", "years_employment": "8",
    "credit_score": "700", "existing_debt": "2000", "dti_ratio": "15", "loan_amount": "10000",
    "loan_term": "36", "previous_loans": "2", "payment_history": "good",
}


@pytest.fixture(scope="module")
def reference():
    return load_json(os.path.join(ARTIFACTS_DIR, REFERENCE_DISTRIBUTION_FILENAME))


@pytest.fixture
def artifacts(tmp_path):
    shutil.copytree(ARTIFACTS_DIR, tmp_path / "artifacts")
    return str(tmp_path / "artifacts")


# PSI

def test_psi_is_zero_for_identical_distributions():
    assert monitor.psi([0.2, 0.3, 0.5], [0.2, 0.3, 0.5]) == pytest.approx(0)


def test_psi_known_value():
    # (0.5 - 0.25) * ln(2) + (0.5 - 0.75) * ln(0.5 / 0.75)
    expected = 0.25 * np.log(2) + (-0.25) * np.log(0.5 / 0.75)
    assert monitor.psi([0.25, 0.75], [0.5, 0.5]) == pytest.approx(expected)


def test_psi_is_symmetric_and_handles_empty_bins():
    assert monitor.psi([0.1, 0.9], [0.4, 0.6]) == pytest.approx(monitor.psi([0.4, 0.6], [0.1, 0.9]))
    assert np.isfinite(monitor.psi([0.5, 0.5, 0.0], [0.0, 0.5, 0.5]))


def test_bin_fractions_put_values_equal_to_a_cut_in_the_lower_bin():
    assert monitor.bin_fractions([1, 2, 3, 4], [2, 3]) == [0.5, 0.25, 0.25]
    assert monitor.bin_fractions([10, 20], []) == [1.0]
    assert monitor.bin_fractions([100], [2, 3]) == [0.0, 0.0, 1.0]  # beyond the range of train: the last bin


@pytest.mark.parametrize("value, status", [(0, "stable"), (0.0999, "stable"), (0.1, "watch"), (0.25, "watch"), (0.2501, "alert"), (3, "alert")])
def test_psi_status_thresholds(value, status):
    assert psi_status(value) == status
    assert (PSI_STABLE, PSI_ALERT) == (0.1, 0.25)


def test_risk_thresholds_match_the_application():
    assert (monitor.APPROVED_MAX, monitor.MEDIUM_MAX) == (config.Config.CREDIT_APPROVED_MAX_RISK, config.Config.CREDIT_MEDIUM_MAX_RISK)
    assert [monitor.label_for(r) for r in (0.1, 0.329, 0.33, 0.659, 0.66, 0.9)] == [
        "Approved", "Approved", "Medium Risk", "Medium Risk", "High Risk", "High Risk"]


# Reference distribution (statistics of train, committed)

def test_reference_distribution_is_valid_small_and_has_no_rows(reference):
    assert validate_reference_distribution(reference) == []
    path = os.path.join(ARTIFACTS_DIR, REFERENCE_DISTRIBUTION_FILENAME)
    assert os.path.getsize(path) < 20_000
    text = open(path, encoding="utf-8").read()
    assert "LoanID" not in text and "SYN" not in text
    assert set(reference["numeric"]) | set(reference["categorical"]) == set(MODEL_FEATURES)


def test_reference_belongs_to_the_trained_models(reference):
    manifest = load_json(os.path.join(ARTIFACTS_DIR, "manifest.json"))
    assert reference["version"] == manifest["version"]
    assert reference["dataset"]["sha256"] == manifest["dataset"]["sha256"]
    assert reference["labels"]["model"] == manifest["champion"]
    assert reference["labels"]["thresholds"] == {"approved_max": monitor.APPROVED_MAX, "medium_max": monitor.MEDIUM_MAX}


def test_reference_validator_rejects_malformed_documents(reference):
    broken = json.loads(json.dumps(reference))
    broken["numeric"]["Age"]["fractions"].pop()
    assert validate_reference_distribution(broken) != []
    assert validate_reference_distribution({}) != []


# Simulated batch and report

def test_simulated_batch_is_reproducible_with_the_same_seed(reference):
    first = monitor.simulated_batch(reference, 500, 42)
    again = monitor.simulated_batch(reference, 500, 42)
    other = monitor.simulated_batch(reference, 500, 7)
    assert first.equals(again) and not first.equals(other)
    assert list(first.columns) == MODEL_FEATURES


def test_without_drift_the_simulated_batch_is_stable(reference):
    batch = monitor.simulated_batch(reference, 3000, 42, drift={})
    assert all(value < PSI_STABLE for value in monitor.batch_psi(batch, reference).values())


def test_the_intentional_drift_is_detected_and_the_rest_stays_stable(reference):
    batch = monitor.simulated_batch(reference, monitor.SIMULATED_ROWS, monitor.SIMULATED_SEED)
    values = monitor.batch_psi(batch, reference)
    assert psi_status(values["CreditScore"]) == "alert"
    assert psi_status(values["LoanAmount"]) == "watch"
    assert all(psi_status(v) == "stable" for name, v in values.items() if name not in monitor.SIMULATED_DRIFT)


def test_the_committed_monitoring_report_is_simulated_valid_and_shows_the_alert():
    report = load_json(os.path.join(ARTIFACTS_DIR, MONITORING_REPORT_FILENAME))
    assert validate_monitoring_report(report) == []
    assert report["source"] == "SIMULATED" and report["simulated"] is True and report["batch"]["seed"] == 42
    assert report["overall_status"] == "alert" and "CreditScore" in report["features_in_alert"]
    assert {item["feature"] for item in report["batch"]["drift_injected"]} == set(monitor.SIMULATED_DRIFT)
    assert "SIMULATED" in report["recommendation"]
    assert validate_artifacts(ARTIFACTS_DIR, require_models=True) == []


def test_run_simulated_writes_a_valid_report(artifacts):
    report = monitor.run(simulated=True, artifacts_dir=artifacts, rows=800)
    written = load_json(os.path.join(artifacts, MONITORING_REPORT_FILENAME))
    assert written == report and validate_monitoring_report(written) == []
    assert report["batch"]["rows"] == 800 and set(report["labels"]["batch"]) == {"Approved", "Medium Risk", "High Risk"}
    assert report["labels"]["difference"]["Approved"] == pytest.approx(
        report["labels"]["batch"]["Approved"] - report["labels"]["reference"]["Approved"], abs=1e-5)


def test_report_from_a_prediction_log_is_not_simulated(artifacts, reference, tmp_path):
    batch = monitor.simulated_batch(reference, 600, 5, drift={})
    log = PredictionLog(str(tmp_path / "predictions.jsonl"))
    rng = np.random.default_rng(1)
    for row, risk in zip(batch.to_dict("records"), rng.uniform(0.05, 0.95, len(batch))):
        log.record("logistic_regression", "lr@x", row, risk, monitor.label_for(risk))
    report = monitor.run(log_path=log.path, artifacts_dir=artifacts)
    assert report["source"] == "PREDICTION_LOG" and report["simulated"] is False
    assert report["batch"]["drift_injected"] == [] and report["batch"]["rows"] == 600
    assert report["batch"]["period"]["from"] <= report["batch"]["period"]["to"]
    assert report["overall_status"] == "stable"


def test_a_small_log_warns_that_the_psi_is_not_reliable(artifacts, reference, tmp_path):
    batch = monitor.simulated_batch(reference, 20, 5, drift={})
    log = PredictionLog(str(tmp_path / "predictions.jsonl"))
    for row in batch.to_dict("records"):
        log.record("logistic_regression", "lr@x", row, 0.4, "Medium Risk")
    report = monitor.run(log_path=log.path, artifacts_dir=artifacts)
    assert "Only 20 predictions" in report["recommendation"] and "sampling noise" in report["recommendation"]


def test_a_large_log_has_no_small_batch_warning(artifacts, reference, tmp_path):
    batch = monitor.simulated_batch(reference, monitor.MIN_RELIABLE_ROWS, 5, drift={})
    log = PredictionLog(str(tmp_path / "predictions.jsonl"))
    for row in batch.to_dict("records"):
        log.record("logistic_regression", "lr@x", row, 0.4, "Medium Risk")
    report = monitor.run(log_path=log.path, artifacts_dir=artifacts)
    assert "sampling noise" not in report["recommendation"]


def test_empty_log_is_rejected(artifacts, tmp_path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        monitor.run(log_path=str(empty), artifacts_dir=artifacts)


def test_monitoring_validator_rejects_inconsistent_reports():
    report = load_json(os.path.join(ARTIFACTS_DIR, MONITORING_REPORT_FILENAME))
    wrong_status = json.loads(json.dumps(report))
    wrong_status["psi"]["Age"]["status"] = "alert"
    assert validate_monitoring_report(wrong_status) != []
    no_drift = json.loads(json.dumps(report))
    no_drift["batch"]["drift_injected"] = []
    assert validate_monitoring_report(no_drift) != []
    mislabeled = json.loads(json.dumps(report))
    mislabeled["simulated"] = False
    assert validate_monitoring_report(mislabeled) != []


def test_monitor_command_line_needs_a_source():
    with pytest.raises(SystemExit):
        monitor.parse_args([])
    assert monitor.parse_args(["--simulated"]).simulated is True
    assert monitor.parse_args(["--log", "x.jsonl"]).log == "x.jsonl"


# Prediction log

@pytest.fixture
def logged(app, tmp_path):
    """The application writing its prediction log in a temporary file."""
    path = tmp_path / "logs" / "predictions.jsonl"
    app.extensions["prediction_log"].path = str(path)
    return path


def _lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_a_credit_evaluation_writes_one_line_without_customer_data(client, demo_user, logged):
    response = client.post("/credit/", data=FORM)
    assert response.status_code == 302
    (record,) = _lines(logged)
    assert tuple(record) == RECORD_KEYS
    assert set(record["inputs"]) == set(MODEL_FEATURES)
    assert record["inputs"]["Age"] == 35 and record["inputs"]["Income"] == 48000 and record["inputs"]["EmploymentType"] == "Full-time"
    assert 0 <= record["probability"] <= 1 and record["label"] in ("Approved", "Medium Risk", "High Risk")
    assert re.fullmatch(r"(lr|rf|xgb)@.+", record["model_version"]) and record["timestamp"].endswith("Z")
    text = logged.read_text(encoding="utf-8")
    assert "Maria" not in text and "100200300" not in text and "client" not in text.lower()


def test_the_log_label_and_probability_match_the_saved_evaluation(client, demo_user, logged):
    client.post("/credit/", data=FORM)
    (saved,) = repository.list_credit_applications(demo_user.id)
    (record,) = _lines(logged)
    assert record["label"] == saved["risk_label"] and record["probability"] * 100 == pytest.approx(saved["risk_percent"], abs=0.06)
    assert record["model_version"] == saved["model_version"]


def test_predictions_of_a_model_tab_are_logged_too(client, demo_user, logged):
    client.post("/credit/models/xgboost/predict", data={k: v for k, v in FORM.items() if not k.startswith("client_")})
    (record,) = _lines(logged)
    assert record["model"] == "xgboost" and record["model_version"].startswith("xgb@")


def test_the_log_is_off_with_an_empty_path(app, client, demo_user, tmp_path):
    app.extensions["prediction_log"].path = ""
    assert client.post("/credit/", data=FORM).status_code == 302
    assert not (tmp_path / "logs").exists()


def test_a_failure_to_write_the_log_never_breaks_the_prediction(app, client, demo_user, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    app.extensions["prediction_log"].path = str(blocker / "predictions.jsonl")  # a folder inside a file
    assert client.post("/credit/", data=FORM).status_code == 302
    assert len(repository.list_credit_applications(demo_user.id)) == 1


def test_the_placeholder_model_writes_no_log(app, client, demo_user, tmp_path, logged):
    registry = ModelRegistry(str(tmp_path / "none"), EXAMPLE_ARTIFACTS_DIR, app.extensions["credit_predictor"], app.extensions["prediction_log"])
    app.extensions["model_registry"] = registry
    client.post("/credit/", data=FORM)
    assert not logged.exists()


def test_the_log_folder_is_ignored_by_git():
    ignored = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read().split()
    assert "logs/" in ignored


def test_the_default_log_path_is_configurable_and_ignored():
    assert config.Config.PREDICTION_LOG_PATH.replace("\\", "/").endswith("logs/predictions.jsonl")
    assert config.TestingConfig.PREDICTION_LOG_PATH == ""
    assert config.Config.PREDICTION_LOG_RETENTION_DAYS == int(os.environ.get("PREDICTION_LOG_RETENTION_DAYS", "90"))


# Retention

def _old_and_new(tmp_path):
    log = PredictionLog(str(tmp_path / "p.jsonl"))
    now = datetime(2026, 11, 13, tzinfo=timezone.utc)
    inputs = {name: 1 for name in MODEL_FEATURES}
    for days in (200, 91, 89, 1, 0):
        log.record("xgboost", "xgb@x", inputs, 0.4, "Medium Risk", now=now - timedelta(days=days))
    return log, now


def test_purge_deletes_only_the_entries_older_than_the_retention(tmp_path):
    log, now = _old_and_new(tmp_path)
    assert log.purge(90, now=now) == (2, 3)
    assert len(_lines(tmp_path / "p.jsonl")) == 3
    assert log.purge(90, now=now) == (0, 3)


def test_summary_counts_the_log(tmp_path):
    log, _now = _old_and_new(tmp_path)
    summary = log.summary()
    assert summary["predictions"] == 5 and summary["by_label"] == {"Medium Risk": 5} and summary["by_model"] == {"xgboost": 5}
    assert PredictionLog(str(tmp_path / "missing.jsonl")).summary() is None and PredictionLog("").summary() is None


def test_purge_command_uses_the_retention_of_the_configuration(app, tmp_path):
    log, now = _old_and_new(tmp_path)
    app.extensions["prediction_log"].path = log.path
    app.config["PREDICTION_LOG_RETENTION_DAYS"] = 2000
    result = app.test_cli_runner().invoke(args=["purge-prediction-log"])
    assert result.exit_code == 0 and "Deleted 0 predictions" in result.output
    result = app.test_cli_runner().invoke(args=["purge-prediction-log", "--days", "10"])
    assert "Deleted 3 predictions older than 10 days; 2 kept." in result.output


# Demo account password

def test_seed_demo_sets_the_password_from_the_environment_setting(app):
    from app.auth.services import authenticate_user

    app.config["DEMO_PASSWORD"] = "first-demo-password"
    assert app.test_cli_runner().invoke(args=["seed-demo"]).exit_code == 0
    app.config["DEMO_PASSWORD"] = "second-demo-password"
    assert app.test_cli_runner().invoke(args=["seed-demo"]).exit_code == 0
    demo = User.query.filter_by(email="demo@creditrisk.local").one()
    assert demo.check_password("second-demo-password") and not demo.check_password("first-demo-password")
    with app.test_request_context():
        assert authenticate_user("demo@creditrisk.local", "second-demo-password") is not None


@pytest.mark.parametrize("value", [None, "", "short"])
def test_seed_demo_needs_a_valid_demo_password(app, value):
    app.config["DEMO_PASSWORD"] = value
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code != 0 and "DEMO_PASSWORD" in result.output
    assert User.query.count() == 0


def test_the_default_demo_password_exists_only_outside_production():
    if "DEMO_PASSWORD" in os.environ:
        pytest.skip("DEMO_PASSWORD is set in this environment")
    assert config.DevelopmentConfig.DEMO_PASSWORD == config.DEFAULT_DEMO_PASSWORD == "demo-password-2026"
    assert config.TestingConfig.DEMO_PASSWORD == "demo-password-2026"
    assert config.ProductionConfig.DEMO_PASSWORD is None


def test_readme_documents_the_demo_password_and_no_longer_says_it_is_random():
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    assert "DEMO_PASSWORD" in readme and "its password is random" not in readme
    assert "PREDICTION_LOG_PATH" in readme and "ml.monitor" in readme
