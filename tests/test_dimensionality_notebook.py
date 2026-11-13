"""Tests for notebooks/credit_risk_dimensionality.ipynb, its report and its figures."""
import base64
import json
import os
import re

import pytest

from ml.features import ARTIFACTS_DIR, MANIFEST_FILENAME
from ml.schemas import (
    DIMENSIONALITY_REPORT_FILENAME,
    load_json,
    validate_artifacts,
    validate_dimensionality_report,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOK = os.path.join(ROOT, "notebooks", "credit_risk_dimensionality.ipynb")
REPORT = os.path.join(ARTIFACTS_DIR, DIMENSIONALITY_REPORT_FILENAME)
FIGURE_DIR = os.path.join(ROOT, "static", "img", "methodology")

COLAB_URL = (
    "https://colab.research.google.com/github/Cristhian731/Credit-Risk/blob/main/"
    "notebooks/credit_risk_dimensionality.ipynb"
)
# Anything that would reveal a local machine, a user account or the tools used to write the work.
FORBIDDEN = (
    "maira", "\\users\\", "/users/", "c:\\", "c:/", "appdata", "onedrive", "site-packages", "ipykernel",
    "claude", "anthropic", "openai", "chatgpt", "copilot", "matplotlib version",
)


@pytest.fixture(scope="module")
def notebook():
    with open(NOTEBOOK, encoding="utf-8") as fh:
        return json.load(fh)


def _strings(notebook):
    """Every text of the notebook: sources, text outputs and decoded images' text chunks."""
    for cell in notebook["cells"]:
        yield "".join(cell["source"])
        for output in cell.get("outputs", []):
            if "text" in output:
                yield "".join(output["text"])
            for mime, value in output.get("data", {}).items():
                if mime.startswith("text/"):
                    yield "".join(value)
            if "traceback" in output:
                yield "\n".join(output["traceback"])


def _png_bytes(notebook):
    for cell in notebook["cells"]:
        for output in cell.get("outputs", []):
            image = output.get("data", {}).get("image/png")
            if image:
                yield base64.b64decode(image)


# Structure

def test_notebook_starts_with_the_open_in_colab_badge_of_main(notebook):
    first = notebook["cells"][0]
    assert first["cell_type"] == "markdown"
    text = "".join(first["source"])
    assert "Open In Colab" in text and COLAB_URL in text


def test_notebook_explains_its_steps_with_markdown(notebook):
    kinds = [cell["cell_type"] for cell in notebook["cells"]]
    assert kinds.count("markdown") >= 10
    assert kinds.count("code") >= 10


def test_notebook_installs_only_the_notebook_requirements_in_colab(notebook):
    source = "\n".join("".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code")
    assert "requirements-notebook.txt" in source
    assert "requirements.txt" not in source.replace("requirements-notebook.txt", "")
    assert "dataset.load" in source and "build_pipeline" in source  # reuses the app code


def test_notebook_deletes_the_test_split(notebook):
    source = "\n".join("".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code")
    assert "del X_test, y_test" in source


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


def test_images_have_no_tool_metadata(notebook):
    images = list(_png_bytes(notebook))
    assert len(images) >= 8
    assert all(b"Matplotlib" not in data and b"Software" not in data for data in images)


# Report and figures

def test_requirements_notebook_matches_the_app_versions():
    def pins(path):
        with open(path, encoding="utf-8") as fh:
            return {
                match.group(1): match.group(2)
                for line in fh
                if (match := re.match(r"([A-Za-z0-9_.-]+)==([0-9.]+)", line.strip()))
            }

    app, notebook_pins = pins(os.path.join(ROOT, "requirements.txt")), pins(os.path.join(ROOT, "requirements-notebook.txt"))
    for package in ("numpy", "pandas", "scikit-learn", "joblib", "xgboost-cpu", "xgboost"):
        assert notebook_pins[package] == app[package]
    assert {"matplotlib", "seaborn"} <= set(notebook_pins)


def test_report_is_valid_and_refers_to_the_champion():
    report = load_json(REPORT)
    assert validate_dimensionality_report(report) == []
    assert report["champion"] == load_json(os.path.join(ARTIFACTS_DIR, MANIFEST_FILENAME))["champion"]
    assert "Train split only" in report["protocol"]["data"]
    assert report["tsne"]["sample_rows"] == 5000 and report["tsne"]["random_state"] == 42


def test_artifact_folder_still_validates_with_the_report():
    assert validate_artifacts(ARTIFACTS_DIR, require_models=True) == []


def test_report_figures_exist_and_have_no_tool_metadata():
    report = load_json(REPORT)
    assert len(report["figures"]) >= 8
    for figure in report["figures"]:
        path = os.path.join(ROOT, "static", "img", *figure.split("/"))
        assert os.path.exists(path), figure
        with open(path, "rb") as fh:
            data = fh.read()
        assert data.startswith(b"\x89PNG") and b"Matplotlib" not in data and b"Software" not in data
    assert set(os.listdir(FIGURE_DIR)) == {os.path.basename(f) for f in report["figures"]}


def test_validator_rejects_malformed_reports():
    assert validate_dimensionality_report({}) != []
    broken = load_json(REPORT)
    broken["experiments"]["without_age"].pop("by_age_range")
    assert validate_dimensionality_report(broken) != []
    broken = load_json(REPORT)
    broken["experiments"]["pca_components"]["variants"] = []
    assert validate_dimensionality_report(broken) != []
