"""Tests for notebooks/credit_risk_clustering.ipynb, clustering_report.json and its figures."""
import copy
import json
import os

import pytest

from ml.features import ARTIFACTS_DIR
from ml.schemas import (
    CLUSTERING_REPORT_FILENAME,
    CLUSTERING_TECHNIQUES,
    load_json,
    validate_artifacts,
    validate_clustering_report,
)
from tests.test_dimensionality_notebook import FORBIDDEN, FIGURE_DIR, ROOT, _forbidden_words, _png_bytes, _strings

NOTEBOOK = os.path.join(ROOT, "notebooks", "credit_risk_clustering.ipynb")
REPORT = os.path.join(ARTIFACTS_DIR, CLUSTERING_REPORT_FILENAME)
COLAB_URL = (
    "https://colab.research.google.com/github/Cristhian731/Credit-Risk/blob/main/"
    "notebooks/credit_risk_clustering.ipynb"
)


@pytest.fixture(scope="module")
def notebook():
    with open(NOTEBOOK, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def report():
    return load_json(REPORT)


def _code(notebook):
    return "\n".join("".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code")


# Structure

def test_notebook_starts_with_the_open_in_colab_badge_of_main(notebook):
    text = "".join(notebook["cells"][0]["source"])
    assert notebook["cells"][0]["cell_type"] == "markdown" and "Open In Colab" in text and COLAB_URL in text


def test_notebook_explains_its_steps_and_uses_the_three_techniques(notebook):
    kinds = [cell["cell_type"] for cell in notebook["cells"]]
    assert kinds.count("markdown") >= 10 and kinds.count("code") >= 10
    source = _code(notebook)
    for needle in ("KMeans", "DBSCAN", "AgglomerativeClustering", "dendrogram", "silhouette_score",
                   "davies_bouldin_score", "calinski_harabasz_score", "NearestNeighbors"):
        assert needle in source


def test_notebook_uses_the_same_setup_and_data_cells_as_the_dimensionality_notebook(notebook):
    with open(os.path.join(ROOT, "notebooks", "credit_risk_dimensionality.ipynb"), encoding="utf-8") as fh:
        other = json.load(fh)
    mine = {"".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"}
    assert "".join(other["cells"][2]["source"]) in mine  # clone and install requirements-notebook.txt
    assert "".join(other["cells"][5]["source"]) in mine  # load, SHA-256 check and split
    source = _code(notebook)
    assert "requirements-notebook.txt" in source
    assert "requirements.txt" not in source.replace("requirements-notebook.txt", "")


def test_notebook_deletes_the_test_split_and_never_clusters_with_the_label(notebook):
    source = _code(notebook)
    assert "del X_test, y_test" in source
    assert ".fit(Zs)" in source and "fit(Zs_s)" in source
    assert "fit(Zs, y_train" not in source and "fit(X_train, y_train" not in source


# Saved outputs

def test_every_code_cell_was_executed_without_errors(notebook):
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is not None
            assert all(output["output_type"] != "error" for output in cell["outputs"])


def test_notebook_metadata_and_outputs_are_clean(notebook):
    assert set(notebook["metadata"]) <= {"kernelspec", "language_info", "colab"}
    assert set(notebook["metadata"]["language_info"]) == {"name"}
    assert all(cell["metadata"] == {} for cell in notebook["cells"])
    for text in _strings(notebook):
        lowered = text.lower()
        for word in FORBIDDEN:
            assert word not in lowered, f"{word!r} found in the notebook"
        assert _forbidden_words(text) == set()


def test_images_have_no_tool_metadata(notebook):
    images = list(_png_bytes(notebook))
    assert len(images) >= 6
    assert all(b"Matplotlib" not in data and b"Software" not in data for data in images)


# Report and figures

def test_report_is_valid_and_part_of_the_artifacts_check():
    assert validate_clustering_report(load_json(REPORT)) == []
    assert validate_artifacts(ARTIFACTS_DIR) == []


def test_report_covers_the_three_techniques_with_metrics_sizes_and_default_rates(report):
    for technique in CLUSTERING_TECHNIQUES:
        metrics = report["comparison"][technique]
        assert metrics["silhouette"] is None or -1 <= metrics["silhouette"] <= 1
        rows = report["clusters"][technique]
        assert sum(row["size"] for row in rows) > 0
        assert all(0 <= row["default_rate"] <= 1 for row in rows)
        assert abs(sum(row["share"] for row in rows) - 1) < 0.01
    assert report["kmeans"]["chosen_k"] in [item["k"] for item in report["kmeans"]["k_candidates"]]


def test_report_uses_only_the_train_split_and_hides_the_label(report):
    assert "Train split only" in report["protocol"]["data"]
    assert "not an input" in report["protocol"]["label_usage"]


def test_report_figures_exist_without_tool_metadata(report):
    assert len(report["figures"]) >= 6
    for figure in report["figures"]:
        path = os.path.join(os.path.dirname(FIGURE_DIR), figure.split("/", 1)[1]) if False else os.path.join(FIGURE_DIR, os.path.basename(figure))
        assert os.path.exists(path), figure
        with open(path, "rb") as fh:
            data = fh.read()
        assert data.startswith(b"\x89PNG") and b"Matplotlib" not in data and b"Software" not in data


def test_validator_rejects_broken_reports(report):
    assert validate_clustering_report({}) != []
    broken = copy.deepcopy(report)
    broken["clusters"]["kmeans"][0]["share"] = 0.9
    assert any("add up to 1" in error for error in validate_clustering_report(broken))
    broken = copy.deepcopy(report)
    broken["kmeans"]["chosen_k"] = 99
    assert any("chosen_k" in error for error in validate_clustering_report(broken))
    broken = copy.deepcopy(report)
    del broken["comparison"]["dbscan"]
    assert validate_clustering_report(broken) != []
    broken = copy.deepcopy(report)
    broken["clusters"]["kmeans"][0]["cluster"] = -1
    assert any("noise" in error for error in validate_clustering_report(broken))
