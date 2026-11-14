"""Tests for ml/evaluate.py."""
import numpy as np
import pytest

from ml.evaluate import ROC_POINTS, evaluate
from ml.schemas import EVALUATION_KEYS



class _FixedProbabilities:
    """Fake fitted model that returns the given default probabilities."""

    def __init__(self, probabilities):
        self.probabilities = np.asarray(probabilities, dtype=float)

    def predict_proba(self, X):
        return np.column_stack([1 - self.probabilities, self.probabilities])


Y = [0, 0, 0, 0, 0, 0, 1, 1, 1, 0]
PROBABILITIES = [0.1, 0.2, 0.3, 0.6, 0.1, 0.2, 0.9, 0.4, 0.8, 0.3]


def test_evaluate_returns_exactly_the_evaluation_keys():
    """The result has the keys test, confusion_matrix and roc_curve, nothing else."""
    result = evaluate(_FixedProbabilities(PROBABILITIES), np.zeros((10, 1)), Y)
    assert set(result) == set(EVALUATION_KEYS)
    assert set(result["test"]) == {"roc_auc", "recall", "precision", "f1", "accuracy"}


def test_confusion_matrix_uses_threshold_0_5():
    """With the fixed probabilities: tn=6, fp=1, fn=1, tp=2."""
    result = evaluate(_FixedProbabilities(PROBABILITIES), np.zeros((10, 1)), Y)
    assert result["confusion_matrix"] == [[6, 1], [1, 2]]
    assert result["test"]["recall"] == pytest.approx(2 / 3)
    assert result["test"]["accuracy"] == pytest.approx(0.8)


def test_roc_curve_is_downsampled_and_goes_from_0_to_1():
    """On 10 000 rows the curve has at most ~ROC_POINTS points, from (0, 0) to (1, 1)."""
    rng = np.random.default_rng(42)
    y = rng.integers(0, 2, 10_000)
    probabilities = np.clip(y * 0.3 + rng.random(10_000) * 0.7, 0, 1)
    curve = evaluate(_FixedProbabilities(probabilities), np.zeros((10_000, 1)), y)["roc_curve"]
    assert len(curve["fpr"]) == len(curve["tpr"]) <= ROC_POINTS + 2
    assert (curve["fpr"][0], curve["tpr"][0]) == (0, 0)
    assert (curve["fpr"][-1], curve["tpr"][-1]) == (1, 1)


def test_result_is_json_serializable():
    """Values are plain Python numbers and lists, so json.dumps works."""
    import json

    json.dumps(evaluate(_FixedProbabilities(PROBABILITIES), np.zeros((10, 1)), Y))
