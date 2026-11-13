"""Public Methodology pages: overview and the six CRISP-ML phases, read from the JSON artifacts."""
import json
import re
import shutil

import pytest
from markupsafe import escape

from app.auth.services import DEMO_EMAIL, register_user
from app.methodology.services import PHASES, TEAM
from ml.features import ARTIFACTS_DIR
from ml.schemas import DISPLAY_NAMES, load_json

PAGES = ["/methodology/"] + [f"/methodology/phase-{number}" for number, _title in PHASES]


@pytest.fixture
def public_client(app, client):
    """Real authentication on and nobody logged in: the pages must still open."""
    app.config["AUTH_ENABLED"] = True
    return client


@pytest.fixture
def artifacts_copy(app, tmp_path, monkeypatch):
    """A copy of the real artifacts that the registry reads, so a test can change a JSON file."""
    shutil.copytree(ARTIFACTS_DIR, tmp_path, dirs_exist_ok=True)
    monkeypatch.setattr(app.extensions["model_registry"], "artifacts_dir", str(tmp_path))
    return tmp_path


def _html(client, path):
    response = client.get(path)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def _change(path, edit):
    document = json.loads(path.read_text(encoding="utf-8"))
    edit(document)
    path.write_text(json.dumps(document), encoding="utf-8")


# Access and menu

@pytest.mark.parametrize("path", PAGES)
def test_pages_are_public(public_client, path):
    assert public_client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/methodology/phase-0", "/methodology/phase-7", "/methodology/phase-x"])
def test_unknown_phase_is_404(public_client, path):
    assert public_client.get(path).status_code == 404


def _methodology_menu(html):
    nav = re.search(r"<nav.*?</nav>", html, re.DOTALL).group(0)
    menu = nav.split('id="methodology-menu"')[1].split("</ul>")[0]
    return re.findall(r'class="dropdown-item" href="([^"]+)">([^<]+)<', menu)


def test_menu_is_visible_without_a_session_with_the_title_of_each_phase(public_client):
    items = _methodology_menu(_html(public_client, "/"))
    assert items[0] == ("/methodology/", "Overview")
    assert items[1:] == [(f"/methodology/phase-{n}", f"Phase {n} &middot; {title}") for n, title in PHASES]


def test_menu_is_visible_with_a_session(public_client, app):
    register_user("ana", "ana@example.com", "correct-horse-battery")
    public_client.post("/auth/login", data={"email": "ana@example.com", "password": "correct-horse-battery"})
    items = _methodology_menu(_html(public_client, "/dashboard/"))
    assert len(items) == 1 + len(PHASES)


@pytest.mark.parametrize("number, title", PHASES)
def test_each_page_shows_its_descriptive_title(public_client, number, title):
    html = _html(public_client, f"/methodology/phase-{number}")
    assert f"Phase {number} &middot; {title}" in html
    assert f"<h1" in html


# Overview

def test_overview_has_the_team_problem_and_links(public_client):
    html = _html(public_client, "/methodology/")
    for person in TEAM:
        assert person in html
    assert "The problem" in html and "The objective" in html
    assert "https://github.com/Cristhian731/Credit-Risk" in html
    assert "colab.research.google.com/github/Cristhian731/Credit-Risk/blob/main/notebooks/credit_risk_dimensionality.ipynb" in html


def test_overview_results_come_from_the_manifest(public_client):
    manifest = load_json(ARTIFACTS_DIR + "/manifest.json")
    html = _html(public_client, "/methodology/")
    assert DISPLAY_NAMES[manifest["champion"]] in html
    for item in manifest["success_criteria"]["results"]:
        assert str(escape(item["criterion"])) in html and str(item["value"]) in html


def test_overview_shows_the_demo_account(app, public_client):
    html = _html(public_client, "/methodology/")
    assert f'data-testid="demo-email">{DEMO_EMAIL}<' in html
    assert f'data-testid="demo-password">{app.config["DEMO_PASSWORD"]}<' in html


def test_overview_without_a_configured_demo_password_shows_no_password(app, public_client):
    app.config["DEMO_PASSWORD"] = None
    html = _html(public_client, "/methodology/")
    assert 'data-testid="demo-password"' not in html and "DEMO_PASSWORD variable is not set" in html


# Figures are read from the artifacts, never typed

def test_phase_1_numbers_follow_the_data_report(public_client, artifacts_copy):
    _change(artifacts_copy / "data_report.json", lambda d: d["before"].update(rows=123456))
    html = _html(public_client, "/methodology/phase-1")
    assert "123,456" in html
    assert "255,347" not in html


def test_phase_1_documents_the_semi_synthetic_limitation_from_the_data(public_client):
    report = load_json(ARTIFACTS_DIR + "/data_report.json")
    count = report["before"]["inconsistencies"]["months_employed_exceed_adult_life"]
    html = _html(public_client, "/methodology/phase-1")
    assert "semi-synthetic" in html and f"{count:,}" in html
    for section in ("Stakeholders", "Questions the model answers", "Feasibility", "Success criteria", "binary classification"):
        assert section in html


def test_phase_2_shows_before_and_after_the_transformations_and_the_notebook(public_client):
    html = _html(public_client, "/methodology/phase-2")
    for text in ("Data quality: before and after", "Before", "After", "Transformations", "Partitions and validation",
                 "Open in Colab", "credit_risk_dimensionality.ipynb", "PCA scree plot", "InterestRate"):
        assert text in html
    assert "img/methodology/pca_scree.png" in html and "img/methodology/tsne_projection.png" in html
    report = load_json(ARTIFACTS_DIR + "/data_report.json")
    assert f"{report['split']['train_rows']:,}" in html


def test_phase_2_without_the_dimensionality_report_says_pending(public_client, artifacts_copy):
    (artifacts_copy / "dimensionality_report.json").unlink()
    html = _html(public_client, "/methodology/phase-2")
    assert 'data-testid="pending"' in html and "dimensionality report is not available" in html


def test_phase_3_shows_every_run_of_every_model(public_client):
    experiments = load_json(ARTIFACTS_DIR + "/experiments.json")
    html = _html(public_client, "/methodology/phase-3")
    for name, entry in experiments["models"].items():
        assert f'data-testid="runs-{name}"' in html
        assert html.count('<tr class="">') + html.count('<tr class="table-success">') >= len(entry["runs"])
    assert "Search spaces and selected values" in html and "Decisions informed by the domain" in html


def test_phase_4_has_metrics_overfitting_bias_and_the_experiment_without_age(public_client):
    html = _html(public_client, "/methodology/phase-4")
    for test_id in ("comparison", "overfitting", "champion", "subgroups", "without-age", "expert-review", "finding-age_bias"):
        assert f'data-testid="{test_id}"' in html
    assert 'id="roc-comparison"' in html and "js/model_charts.js" in html
    assert "accuracy" in html.lower() and "Success criteria" in html


def test_phase_4_expert_review_is_pending_until_it_is_filled(public_client):
    html = _html(public_client, "/methodology/phase-4")
    section = html.split('data-testid="expert-review"')[1].split("</section>")[0]
    assert "Pending" in section and "has not been done yet" in section


def test_phase_4_expert_review_complete_shows_the_expert(app, public_client, tmp_path):
    review = tmp_path / "review.md"
    review.write_text(
        "---\nstatus: complete\nname: Ana Perez\nrole: Credit analyst\norganization: Sample Bank\ndate: 2026-11-20\n---\n"
        "Q1. Do the variables make sense?\nAnswer: Yes.\n",
        encoding="utf-8",
    )
    app.config["EXPERT_REVIEW_PATH"] = str(review)
    html = _html(public_client, "/methodology/phase-4")
    section = html.split('data-testid="expert-review"')[1].split("</section>")[0]
    assert "Ana Perez" in section and "Credit analyst" in section and "Sample Bank" in section and "2026-11-20" in section
    assert "Answer: Yes." in section and "has not been done yet" not in section


@pytest.mark.parametrize("header", ["status: pending\nname: Ana Perez\ndate: 2026-11-20", "status: complete\nname:\ndate: 2026-11-20"])
def test_phase_4_expert_review_stays_pending_if_incomplete(app, public_client, tmp_path, header):
    review = tmp_path / "review.md"
    review.write_text(f"---\n{header}\n---\nbody\n", encoding="utf-8")
    app.config["EXPERT_REVIEW_PATH"] = str(review)
    section = _html(public_client, "/methodology/phase-4").split('data-testid="expert-review"')[1]
    assert "has not been done yet" in section


def test_the_repository_expert_review_file_is_the_pending_template(public_client):
    path = "docs/expert_review.md"
    text = open(path, encoding="utf-8").read()
    assert text.startswith("---\nstatus: pending")
    assert len(re.findall(r"^Q\d\.", text, re.M)) in (6, 7, 8)


def test_phase_5_has_inputs_outputs_dependencies_instructions_and_the_finance_flow(public_client):
    html = _html(public_client, "/methodology/phase-5")
    for test_id in ("pipeline", "inputs-outputs", "dependencies", "run-instructions", "user-instructions", "activity2", "procedures"):
        assert f'data-testid="{test_id}"' in html
    assert "Check my credit risk" in html and "model.joblib" in html
    assert "scikit-learn" in html and "incidents" in html.lower() and "Feedback" in html


def test_phase_6_has_indicators_thresholds_the_simulated_report_and_the_retention_policy(app, public_client):
    html = _html(public_client, "/methodology/phase-6")
    for test_id in ("indicators", "drift", "maintenance", "retention", "simulated-banner", "overall-status"):
        assert f'data-testid="{test_id}"' in html
    assert "SIMULATED" in html and 'id="psi-chart"' in html
    assert "below 0.1" in html and "above 0.25" in html
    retention = html.split('data-testid="retention-days">')[1].split("<")[0]
    assert retention == f"{app.config['PREDICTION_LOG_RETENTION_DAYS']} days"


def test_phase_6_follows_the_monitoring_report(public_client, artifacts_copy):
    _change(artifacts_copy / "monitoring_report.json", lambda d: d["batch"].update(rows=777))
    assert "777 rows" in _html(public_client, "/methodology/phase-6")


def test_phase_6_without_the_report_says_pending(public_client, artifacts_copy):
    (artifacts_copy / "monitoring_report.json").unlink()
    html = _html(public_client, "/methodology/phase-6")
    assert "monitoring report is not available" in html and 'data-testid="simulated-banner"' not in html


def test_phase_6_retention_follows_the_configuration(app, public_client):
    app.config["PREDICTION_LOG_RETENTION_DAYS"] = 30
    assert "30 days" in _html(public_client, "/methodology/phase-6")


def test_pages_say_example_data_without_trained_models(app, public_client, tmp_path, monkeypatch):
    monkeypatch.setattr(app.extensions["model_registry"], "artifacts_dir", str(tmp_path))
    for path in PAGES:
        html = _html(public_client, path)
        assert 'data-testid="example-banner"' in html
