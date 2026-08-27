"""Command-line runner for offline Researcher assessment evaluation."""

import argparse
import json
from pathlib import Path
from typing import Any

from citeguard.evaluation.researcher import (
    ResearcherGoldDataset,
    ResearcherPredictionSet,
    evaluate_assessments,
)


def load_gold_dataset(path: Path) -> ResearcherGoldDataset:
    """Load and validate one versioned Researcher Gold JSON file."""

    return ResearcherGoldDataset.model_validate(_load_json(path))


def load_predictions(path: Path) -> ResearcherPredictionSet:
    """Load and validate system predictions for one Gold dataset."""

    return ResearcherPredictionSet.model_validate(_load_json(path))


def run(dataset_path: Path, predictions_path: Path) -> dict[str, object]:
    """Evaluate one prediction file against one Gold dataset file."""

    return evaluate_assessments(
        load_gold_dataset(dataset_path),
        load_predictions(predictions_path),
    )


def main() -> None:
    """Parse CLI arguments, run metrics, and print or save a JSON report."""

    parser = argparse.ArgumentParser(
        description="Evaluate Researcher paper relevance and MEG selection."
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = run(args.dataset, args.predictions)
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(serialized, end="")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized, encoding="utf-8")


def _load_json(path: Path) -> Any:
    """Read one UTF-8 JSON document without accepting trailing text."""

    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


if __name__ == "__main__":
    main()
