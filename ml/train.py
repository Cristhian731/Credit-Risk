"""Train the three candidate models, pick the champion and save the artifacts.

Owner: ml (Sprint 1). Usage from the project root:

    python -m ml.train [--data ml/data/raw/Loan_default.csv] [--out ml/artifacts]

Output layout (see docs/ML_PHASE.md and ml.schemas):

    <out>/manifest.json
    <out>/<model name>/model.joblib
    <out>/<model name>/metrics.json
"""
import argparse

from ml.dataset import DEFAULT_DATA_PATH
from ml.features import ARTIFACTS_DIR

CV_FOLDS = 5
# Models whose mean CV ROC AUC is less than this below the best one are tied;
# among them the higher mean CV recall (class 1) wins.
CHAMPION_AUC_MARGIN = 0.01


def select_champion(metrics_by_model):
    """Pick the official model using cross-validation results only.

    Rule: highest mean CV ROC AUC (5-fold stratified, train split). Every
    model whose mean CV ROC AUC is less than ``CHAMPION_AUC_MARGIN`` below
    the best one stays in the race, and among them the highest mean CV
    recall of class 1 wins. A remaining tie goes to the first model in
    ``ml.schemas.MODEL_NAMES`` order. Test metrics are never used here.

    Args:
        metrics_by_model: ``{model name: metrics.json content}``.

    Returns:
        The champion's model name.

    Raises:
        ValueError: If ``metrics_by_model`` is empty.
    """
    raise NotImplementedError("Sprint 1 - owner: ml")


def run(data_path=DEFAULT_DATA_PATH, out_dir=ARTIFACTS_DIR):
    """Load, split, cross-validate, fit, evaluate and save every model.

    Writes the layout described in the module docstring, with the dataset
    SHA-256 in ``manifest["dataset"]``, and returns the manifest dict. The
    result must pass ``ml.schemas.validate_artifacts(out_dir)``.
    """
    raise NotImplementedError("Sprint 1 - owner: ml")


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
