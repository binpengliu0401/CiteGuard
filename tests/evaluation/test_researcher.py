"""Verify Researcher Gold contracts and paper-plus-MEG metrics."""

import unittest
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from citeguard.evaluation.researcher import (
    FACTOR_FIELDS,
    GoldAssessment,
    GroupLabel,
    PredictedAssessment,
    PredictedMegCase,
    ResearcherPredictionSet,
    evaluate_assessments,
)
from citeguard.evaluation.runner import load_gold_dataset, load_predictions, run
from citeguard.researcher.relevance import ConstraintMatch, RelevanceLevel

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

    def test_draft_dataset_has_twelve_agent_memory_annotations(self) -> None:
        self.assertEqual(self.dataset.annotation_status, "draft")
        self.assertEqual(self.dataset.schema_version, "5")
        self.assertEqual(self.dataset.subquestion_origin, "manual")
        self.assertEqual(
            self.dataset.evaluation_scope,
            "researcher_meg_mechanism_only",
        )
        self.assertEqual(
            set(self.dataset.open_adjudications),
            {
                "memory-r1-control__a-mem paper and singleton support labels",
                "tier-to-agentic evolution-relation group and MEG labels",
                "three-stage-control evolution-relation group and MEG labels",
            },
        )
        self.assertEqual(self.dataset.version, "0.6.0-draft")
        self.assertEqual(len(self.dataset.cases), 3)
        self.assertEqual(len(self.dataset.items), 12)
        self.assertEqual(
            {len(case.gold_megs[0]) for case in self.dataset.cases},
            {1, 2, 3},
        )
        self.assertTrue(
            all(
                len(case.candidate_item_ids) == 4
                for case in self.dataset.cases
            )
        )
        cases_by_id = {
            case.case_id: case for case in self.dataset.cases
        }
        self.assertIn("2026", cases_by_id["tier-to-agentic"].subquestion)
        self.assertIn("2026", cases_by_id["three-stage-control"].subquestion)
        items_by_id = {
            item.item_id: item for item in self.dataset.items
        }
        self.assertIs(
            items_by_id["tier-to-agentic__survey"].constraint_match,
            ConstraintMatch.FULL,
        )
        self.assertIs(
            items_by_id["three-stage-control__memcon"].constraint_match,
            ConstraintMatch.FULL,
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
        raw_dataset = self.dataset.model_dump(mode="json")
        raw_dataset["annotation_status"] = "reviewed"

        with self.assertRaisesRegex(ValidationError, "open adjudications"):
            type(self.dataset).model_validate(raw_dataset)

    def test_gold_relevance_must_match_gold_factors(self) -> None:
        raw_item = self.dataset.items[0].model_dump(mode="json")
        raw_item["gold_relevance"] = RelevanceLevel.PARTIAL.value

        with self.assertRaisesRegex(ValidationError, "factor-derived"):
            GoldAssessment.model_validate(raw_item)

        raw_item["gold_relevance"] = RelevanceLevel.UNKNOWN.value
        with self.assertRaisesRegex(ValidationError, "not a Gold label"):
            GoldAssessment.model_validate(raw_item)

    def test_gold_megs_must_be_minimum_full_groups(self) -> None:
        raw_case = self.dataset.cases[1].model_dump(mode="json")
        singleton = next(
            item
            for item in raw_case["group_assessments"]
            if len(item["source_ids"]) == 1
        )
        singleton["support"] = "full"

        with self.assertRaisesRegex(ValidationError, "minimum FULL"):
            type(self.dataset.cases[1]).model_validate(raw_case)

    def test_perfect_predictions_score_papers_groups_and_megs(self) -> None:
        predictions = ResearcherPredictionSet(
            dataset_id=self.dataset.dataset_id,
            dataset_version=self.dataset.version,
            system_id="perfect-test-system",
            predictions=[
                self._prediction_from_gold(item) for item in self.dataset.items
            ],
            meg_predictions=[
                PredictedMegCase(
                    case_id=case.case_id,
                    group_assessments=[
                        GroupLabel(
                            source_ids=label.source_ids,
                            support=label.support,
                        )
                        for label in case.group_assessments
                    ],
                    predicted_megs=case.gold_megs,
                )
                for case in self.dataset.cases
            ],
        )

        report = evaluate_assessments(self.dataset, predictions)
        factor_accuracy = cast(
            dict[str, object],
            report["factor_accuracy"],
        )
        relevance = cast(dict[str, object], report["relevance"])
        group_support = cast(dict[str, object], report["group_support"])
        meg = cast(dict[str, object], report["meg"])

        self.assertEqual(factor_accuracy["overall"], 1.0)
        self.assertEqual(relevance["accuracy"], 1.0)
        self.assertEqual(relevance["macro_f1"], 1.0)
        self.assertEqual(group_support["macro_f1"], 1.0)
        self.assertEqual(meg["complete_case_rate"], 1.0)
        self.assertEqual(meg["mean_cardinality_error"], 0.0)
        self.assertEqual(meg["redundant_source_rate"], 0.0)

    def test_fixture_has_one_abstention_and_perfect_meg_selection(self) -> None:
        report = run(DATASET_PATH, PREDICTIONS_PATH)
        relevance = cast(dict[str, object], report["relevance"])
        confusion = cast(
            dict[str, dict[str, int]],
            relevance["confusion_matrix"],
        )
        per_class = cast(dict[str, object], relevance["per_class"])
        group_support = cast(dict[str, object], report["group_support"])
        meg = cast(dict[str, object], report["meg"])

        self.assertEqual(
            relevance["unknown_abstention_rate"],
            0.083333,
        )
        self.assertEqual(confusion["irrelevant"]["unknown"], 1)
        self.assertNotIn("unknown", per_class)
        self.assertEqual(group_support["macro_f1"], 1.0)
        self.assertEqual(meg["complete_case_rate"], 1.0)
        self.assertEqual(meg["mean_cardinality_error"], 0.0)
        self.assertEqual(meg["redundant_source_rate"], 0.0)

    def test_predictions_require_exact_coverage(self) -> None:
        predictions = load_predictions(PREDICTIONS_PATH)
        incomplete_items = predictions.model_copy(
            update={"predictions": predictions.predictions[:-1]}
        )
        with self.assertRaisesRegex(ValueError, "missing="):
            evaluate_assessments(self.dataset, incomplete_items)

        incomplete_cases = predictions.model_copy(
            update={"meg_predictions": predictions.meg_predictions[:-1]}
        )
        with self.assertRaisesRegex(ValueError, "missing="):
            evaluate_assessments(self.dataset, incomplete_cases)

        first_case = predictions.meg_predictions[0]
        incomplete_groups = first_case.model_copy(
            update={"group_assessments": first_case.group_assessments[:-1]}
        )
        wrong_groups = predictions.model_copy(
            update={
                "meg_predictions": [
                    incomplete_groups,
                    *predictions.meg_predictions[1:],
                ]
            }
        )
        with self.assertRaisesRegex(ValueError, "group IDs"):
            evaluate_assessments(self.dataset, wrong_groups)

        wrong_version = predictions.model_copy(
            update={"dataset_version": "wrong-version"}
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
