"""Tests for the model pages /credit/models/ and /credit/models/<name>/ and the credit menu."""
import re

import pytest

from app.auth.services import register_user
from ml.schemas import DISPLAY_NAMES, MODEL_NAMES

SPRINT_2_WEB = pytest.mark.skip(reason="Sprint 2 - owner: web")

EMAIL = "ana@example.com"
PASSWORD = "correct-horse-battery"
PAGES = ["/credit/models/"] + [f"/credit/models/{name}/" for name in MODEL_NAMES]


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

@pytest.mark.parametrize("path", PAGES)
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


# Content with the example artifacts

def test_comparison_lists_the_three_models_with_example_banner(demo_client, example_only):
    html = demo_client.get("/credit/models/").get_data(as_text=True)
    assert "Example data" in html
    for name in MODEL_NAMES:
        assert DISPLAY_NAMES[name] in html
        assert f'href="/credit/models/{name}/"' in html
    assert "Official model" in html


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_detail_shows_the_model_with_example_banner(demo_client, example_only, name):
    html = demo_client.get(f"/credit/models/{name}/").get_data(as_text=True)
    assert "Example data" in html
    assert DISPLAY_NAMES[name] in html
    assert "Confusion matrix" in html


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
    assert 'href="/credit/models/"' in nav


def test_credit_form_still_works_as_before(demo_client):
    html = demo_client.get("/credit/").get_data(as_text=True)
    assert 'name="credit_score"' in html
    assert 'href="/credit/history"' in html


# Skeleton tests for the web owner

@SPRINT_2_WEB
def test_comparison_draws_the_roc_curves_with_chart_js(demo_client):
    """/credit/models/ has a <canvas id="roc-comparison"> and passes the three curves as JSON."""
    html = demo_client.get("/credit/models/").get_data(as_text=True)
    assert 'id="roc-comparison"' in html
    assert "chart.js" in html.lower()


@SPRINT_2_WEB
@pytest.mark.parametrize("name", MODEL_NAMES)
def test_detail_draws_roc_and_feature_importance(demo_client, name):
    """Each detail page has <canvas id="roc-chart"> and <canvas id="importance-chart">."""
    html = demo_client.get(f"/credit/models/{name}/").get_data(as_text=True)
    assert 'id="roc-chart"' in html
    assert 'id="importance-chart"' in html


@SPRINT_2_WEB
def test_no_chart_placeholders_remain(demo_client):
    """No page keeps a data-todo block or the text 'Chart pending'."""
    for path in PAGES:
        html = demo_client.get(path).get_data(as_text=True)
        assert "data-todo" not in html
        assert "Chart pending" not in html


@SPRINT_2_WEB
def test_comparison_explains_the_selection_rule_and_highlights_the_champion(demo_client):
    """The champion row is highlighted and the page explains CV-based selection."""
    html = demo_client.get("/credit/models/").get_data(as_text=True)
    assert "table-success" in html
    assert "cross-validation" in html.lower()
