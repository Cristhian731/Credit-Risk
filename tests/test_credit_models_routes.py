"""Tests for the tabbed model page /credit/models/, the old /credit/models/<name>/ addresses and the credit menu."""
import re

import pytest

from app.auth.services import register_user
from ml.schemas import DISPLAY_NAMES, MODEL_NAMES

EMAIL = "ana@example.com"
PASSWORD = "correct-horse-battery"
PAGES = ["/credit/models/"]
OLD_DETAIL_PAGES = [f"/credit/models/{name}/" for name in MODEL_NAMES]
TABS = list(MODEL_NAMES) + ["comparison"]

FORM = {
    "age": "35", "monthly_income": "4000", "employment_status": "employed", "years_employment": "8",
    "credit_score": "760", "existing_debt": "2000", "dti_ratio": "15", "loan_amount": "10000",
    "loan_term": "36", "previous_loans": "2", "payment_history": "good",
}


@pytest.fixture
def demo_client(client, demo_user):
    """Demo mode (AUTH_ENABLED False): every page runs as the demo user."""
    return client


@pytest.fixture
def example_only(app, tmp_path, monkeypatch):
    """Point the registry to an empty folder, as before the first training run."""
    monkeypatch.setattr(app.extensions["model_registry"], "artifacts_dir", str(tmp_path))


@pytest.fixture
def auth_on(app):
    app.config["AUTH_ENABLED"] = True


def _nav(html):
    return re.search(r"<nav.*?</nav>", html, re.DOTALL).group(0)


# Access

@pytest.mark.parametrize("path", PAGES + OLD_DETAIL_PAGES)
def test_model_pages_require_login(client, auth_on, path):
    response = client.get(path)
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/login")


@pytest.mark.parametrize("path", PAGES)
def test_model_pages_open_after_login(client, auth_on, path):
    register_user("ana", EMAIL, PASSWORD)
    client.post("/auth/login", data={"email": EMAIL, "password": PASSWORD})
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("name", ["svm", "XGBoost", "manifest.json", "_example"])
def test_unknown_model_name_is_404(demo_client, name):
    assert demo_client.get(f"/credit/models/{name}/").status_code == 404
    assert demo_client.post(f"/credit/models/{name}/predict", data=FORM).status_code == 404


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_old_model_address_redirects_to_its_tab(demo_client, name):
    response = demo_client.get(f"/credit/models/{name}/")
    assert response.status_code == 302
    assert response.headers["Location"] == f"/credit/models/#{name}"


# Content with the example artifacts

def test_page_has_the_four_tabs_in_order(demo_client):
    html = demo_client.get("/credit/models/").get_data(as_text=True)
    targets = re.findall(r'data-bs-target="#([a-z_]+)"', html)
    assert targets == TABS
    labels = re.findall(r'role="tab"[^>]*>([^<]+)</button>', html)
    assert [label.strip() for label in labels] == [DISPLAY_NAMES[n] for n in MODEL_NAMES] + ["Comparison"]
    for tab in TABS:
        assert f'id="{tab}" role="tabpanel"' in html


def test_comparison_lists_the_three_models_with_example_banner(demo_client, example_only):
    html = demo_client.get("/credit/models/").get_data(as_text=True)
    assert "Example data" in html
    for name in MODEL_NAMES:
        assert DISPLAY_NAMES[name] in html
        assert f'href="#{name}"' in html
    assert "Official model" in html


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_each_tab_shows_the_model_with_example_banner(demo_client, example_only, name):
    html = demo_client.get("/credit/models/").get_data(as_text=True)
    pane = html.split(f'id="{name}" role="tabpanel"')[1].split('role="tabpanel"')[0]
    assert "Example data" in html
    assert DISPLAY_NAMES[name] in pane
    assert "Confusion matrix" in pane
    # Each owner replaces the base text, so only the section title is required.
    assert "About this algorithm" in pane


def test_example_banner_disappears_with_trained_models(app, demo_client, monkeypatch):
    registry = app.extensions["model_registry"]
    monkeypatch.setattr(registry, "artifacts_dir", registry.example_dir)
    assert "Example data" not in demo_client.get("/credit/models/").get_data(as_text=True)


# Credit menu in the navbar

def test_credit_menu_lists_prediction_models_and_comparison_in_order(demo_client):
    nav = _nav(demo_client.get("/credit/").get_data(as_text=True))
    items = [label.strip() for label in re.findall(r'class="dropdown-item"[^>]*>([^<]+)<', nav)]
    assert items == (
        ["New evaluation (official model)"]
        + [DISPLAY_NAMES[name] for name in MODEL_NAMES]
        + ["Model Comparison"]
    )


def test_credit_menu_links_to_each_tab(demo_client):
    nav = _nav(demo_client.get("/credit/").get_data(as_text=True))
    hrefs = re.findall(r'class="dropdown-item" href="([^"]+)"', nav)
    assert hrefs == ["/credit/"] + [f"/credit/models/#{tab}" for tab in TABS]


def test_credit_form_still_works_as_before(demo_client):
    html = demo_client.get("/credit/").get_data(as_text=True)
    assert 'name="credit_score"' in html
    assert 'href="/credit/history"' in html


def test_credit_form_says_usd_and_monthly_income(demo_client):
    html = demo_client.get("/credit/").get_data(as_text=True)
    assert "US dollars (USD)" in html
    assert "Monthly Income (USD per month)" in html
    assert "Loan Amount (USD)" in html


# Charts, explanation and the per-model form

def test_comparison_draws_the_roc_curves_with_chart_js(demo_client):
    html = demo_client.get("/credit/models/").get_data(as_text=True)
    assert 'id="roc-comparison"' in html and 'id="cv-metrics-chart"' in html
    assert "chart.js" in html.lower()
    assert "js/model_charts.js" in html


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_each_tab_draws_roc_and_feature_importance(demo_client, name):
    html = demo_client.get("/credit/models/").get_data(as_text=True)
    assert f'id="roc-chart-{name}"' in html
    assert f'id="importance-chart-{name}"' in html


def test_no_chart_placeholders_remain(demo_client):
    for path in PAGES:
        html = demo_client.get(path).get_data(as_text=True)
        assert "data-todo" not in html
        assert "Chart pending" not in html


def test_comparison_explains_the_selection_rule_and_highlights_the_champion(demo_client):
    html = demo_client.get("/credit/models/").get_data(as_text=True)
    assert "table-success" in html
    assert "cross-validation" in html.lower()
    assert "Tied with the best" in html


def test_comparison_explains_the_tie_break(demo_client):
    """With the real artifacts the champion is within 0.01 of a better model and wins on recall."""
    html = demo_client.get("/credit/models/").get_data(as_text=True)
    selection = html.split('data-testid="selection-rule"')[1].split("ROC curves")[0]
    assert "closer than" in selection and "highest mean CV recall" in selection


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_each_tab_shows_experiments_and_overfitting(demo_client, name):
    html = demo_client.get("/credit/models/").get_data(as_text=True)
    assert f'data-testid="runs-{name}"' in html
    assert f'data-testid="overfitting-{name}"' in html
    assert "Selected hyperparameters" in html


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_tab_form_predicts_with_that_model_and_saves_nothing(demo_client, demo_user, name):
    from app.services import repository

    response = demo_client.post(f"/credit/models/{name}/predict", data=FORM)
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert f'data-testid="predict-result-{name}"' in html
    assert re.search(r"(Approved|Medium Risk|High Risk)</strong> &middot; estimated default risk", html)
    assert f'class="tab-pane fade show active" id="{name}"' in html
    assert repository.list_credit_applications(demo_user.id) == []


def test_tab_form_reports_invalid_values_without_a_result(demo_client):
    response = demo_client.post("/credit/models/xgboost/predict", data={**FORM, "credit_score": "900"})
    html = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "must be between" in html
    assert 'data-testid="predict-result-xgboost"' not in html


def test_tab_form_without_trained_models_answers_503(demo_client, example_only):
    response = demo_client.post("/credit/models/xgboost/predict", data=FORM)
    assert response.status_code == 503
    assert "not available" in response.get_data(as_text=True)


# "About this algorithm": written text, values read from the JSON artifacts

REFERENCE_DOIS = {
    "logistic_regression": ["10.1111/j.2517-6161.1958.tb00292.x", "10.1002/9781118548387"],
    "random_forest": ["10.1023/A:1010933404324"],
    "xgboost": ["10.1145/2939672.2939785"],
}


def _about(html, name):
    return html.split(f'data-testid="about-{name}"')[1].split("Try ")[0]


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_about_section_is_written_and_has_no_placeholder(demo_client, name):
    section = _about(demo_client.get("/credit/models/").get_data(as_text=True), name)
    assert "TODO" not in section and "Owner:" not in section
    for heading in ("How it works", "Why it fits this problem", "Strengths and limits", "Hyperparameters in this tab", "References"):
        assert heading in section


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_about_section_has_150_to_250_words(demo_client, name):
    section = _about(demo_client.get("/credit/models/").get_data(as_text=True), name).split("References")[0]
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", section))
    assert 150 <= len(text.split()) <= 250


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_about_section_cites_its_references_with_doi(demo_client, name):
    section = _about(demo_client.get("/credit/models/").get_data(as_text=True), name)
    for doi in REFERENCE_DOIS[name]:
        assert f"https://doi.org/{doi}" in section


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_about_section_shows_the_selected_hyperparameters_and_metrics_from_the_json(app, demo_client, name):
    catalog = app.extensions["model_registry"].catalog()
    section = _about(demo_client.get("/credit/models/").get_data(as_text=True), name)
    selected = next(run for run in catalog["experiments"]["models"][name]["runs"] if run["selected"])
    for key, value in selected["params"].items():
        assert f"<code>{key}</code>" in section
        assert f"Selected: <code>{value}</code>" in section
    metrics = catalog["metrics"][name]
    assert f"{metrics['cv']['roc_auc'][0]:.3f}" in section
    assert f"{metrics['cv']['recall'][0]:.3f}" in section


def test_about_section_follows_the_artifacts_when_they_change(app, demo_client, tmp_path, monkeypatch):
    """Nothing is typed by hand: with other artifacts the numbers in the text change."""
    import json
    import shutil

    from ml.features import ARTIFACTS_DIR

    shutil.copytree(ARTIFACTS_DIR, tmp_path, dirs_exist_ok=True)
    path = tmp_path / "xgboost" / "metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    metrics["cv"]["roc_auc"][0] = 0.6123
    path.write_text(json.dumps(metrics), encoding="utf-8")
    monkeypatch.setattr(app.extensions["model_registry"], "artifacts_dir", str(tmp_path))
    section = _about(demo_client.get("/credit/models/").get_data(as_text=True), "xgboost")
    assert "0.612" in section
