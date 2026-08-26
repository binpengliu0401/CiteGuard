"""Verify Researcher Gold contracts and factorized assessment metrics."""

import unittest
from pathlib import Path

from pydantic import ValidationError

from citeguard.evaluation.researcher import (
    FACTOR_FIELDS,
    GoldAssessment,
    PredictedAssessment,
    ResearcherPredictionSet,
    evaluate_assessments,
)
from citeguard.evaluation.runner import load_gold_dataset, load_predictions, run
from citeguard.researcher.relevance import RelevanceLevel


PROJECT_ROOT = Path(__file__).parents[2]
DATASET_PATH = (
    PROJECT_ROOT / "eval" / "datasets" / "researcher_assessment_draft_v0.json"
)
PREDICTIONS_PATH = (
    PROJECT_ROOT
    / "eval"
    / "fixtures"
    / "researcher_assessment_predictions_v0.json"
)


class ResearcherEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = load_gold_dataset(DATASET_PATH)

    def test_draft_dataset_contains_three_atomic_subquestions(self) -> None:
        expected_subquestions = {
            "What scientific claim-verification task does SciFact define?",
            "How is each example in the SciFact dataset represented?",
            "What do the baseline experiments reported for SciFact "
            "establish?",
        }
        expected_source_ids = {
            "2004.14974v6",
            "2112.01640v2",
            "1803.05355v3",
            "1908.10084v1",
        }

        self.assertEqual(self.dataset.annotation_status, "draft")
        self.assertEqual(self.dataset.subquestion_origin, "manual")
        self.assertEqual(self.dataset.version, "0.4.0-draft")
        self.assertEqual(len(self.dataset.items), 12)
        self.assertEqual(
            {item.subquestion for item in self.dataset.items},
            expected_subquestions,
        )
        self.assertTrue(
            all(item.original_question.strip() for item in self.dataset.items)
        )
        for subquestion in expected_subquestions:
            items = [
                item
                for item in self.dataset.items
                if item.subquestion == subquestion
            ]
            self.assertEqual(
                {item.source_id for item in items},
                expected_source_ids,
            )
            self.assertEqual(
                sum(
                    item.gold_relevance is RelevanceLevel.DIRECT
                    for item in items
                ),
                1,
            )
        self.assertEqual(
            {item.gold_relevance for item in self.dataset.items},
            {
                RelevanceLevel.DIRECT,
                RelevanceLevel.PARTIAL,
                RelevanceLevel.BACKGROUND,
                RelevanceLevel.IRRELEVANT,
            },
        )
        self.assertTrue(
            all(
                "/abs/" in item.source_version_url
                for item in self.dataset.items
            )
        )

    def test_gold_relevance_must_match_gold_factors(self) -> None:
        raw_item = self.dataset.items[0].model_dump(mode="json")
        raw_item["gold_relevance"] = RelevanceLevel.PARTIAL.value

        with self.assertRaisesRegex(ValidationError, "factor-derived"):
            GoldAssessment.model_validate(raw_item)

        raw_item["gold_relevance"] = RelevanceLevel.UNKNOWN.value
        with self.assertRaisesRegex(ValidationError, "not a Gold label"):
            GoldAssessment.model_validate(raw_item)

    def test_perfect_predictions_score_every_factor_and_class(self) -> None:
        predictions = ResearcherPredictionSet(
            dataset_id=self.dataset.dataset_id,
            dataset_version=self.dataset.version,
            system_id="perfect-test-system",
            predictions=[
                self._prediction_from_gold(item) for item in self.dataset.items
            ],
        )

        report = evaluate_assessments(self.dataset, predictions)

        self.assertEqual(report["factor_accuracy"]["overall"], 1.0)
        self.assertEqual(report["relevance"]["accuracy"], 1.0)
        self.assertEqual(report["relevance"]["macro_f1"], 1.0)
        self.assertEqual(report["relevance"]["direct_precision"], 1.0)
        self.assertEqual(report["relevance"]["unknown_abstention_rate"], 0.0)

    def test_unknown_is_abstention_and_gold_false_negative(self) -> None:
        report = run(DATASET_PATH, PREDICTIONS_PATH)

        self.assertEqual(
            report["relevance"]["unknown_abstention_rate"],
            0.083333,
        )
        self.assertEqual(report["relevance"]["macro_f1"], 0.95)
        self.assertEqual(
            report["relevance"]["confusion_matrix"]["irrelevant"]["unknown"],
            1,
        )
        self.assertNotIn("unknown", report["relevance"]["per_class"])

    def test_predictions_must_match_dataset_identity_and_item_ids(self) -> None:
        predictions = load_predictions(PREDICTIONS_PATH)
        incomplete = ResearcherPredictionSet(
            dataset_id=predictions.dataset_id,
            dataset_version=predictions.dataset_version,
            system_id=predictions.system_id,
            predictions=predictions.predictions[:-1],
        )

        with self.assertRaisesRegex(ValueError, "missing="):
            evaluate_assessments(self.dataset, incomplete)

        wrong_version = ResearcherPredictionSet(
            dataset_id=predictions.dataset_id,
            dataset_version="wrong-version",
            system_id=predictions.system_id,
            predictions=predictions.predictions,
        )
        with self.assertRaisesRegex(ValueError, "dataset_version"):
            evaluate_assessments(self.dataset, wrong_version)

    @staticmethod
    def _prediction_from_gold(item: GoldAssessment) -> PredictedAssessment:
        return PredictedAssessment(
            item_id=item.item_id,
            **{field: getattr(item, field) for field in FACTOR_FIELDS},
        )


if __name__ == "__main__":
    unittest.main()
