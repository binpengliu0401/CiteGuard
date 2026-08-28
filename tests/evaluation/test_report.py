"""Verify the fixed Writer and Verifier Gold fixture."""

import unittest
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

from citeguard.domain.report import VerificationIssueType
from citeguard.evaluation.report import (
    WriterVerifierCaseKind,
    WriterVerifierGoldDataset,
)
from citeguard.verifier.contracts import VerifierInput
from citeguard.verifier.verification import verify_report

PROJECT_ROOT = Path(__file__).parents[2]
DATASET_PATH = (
    PROJECT_ROOT
    / "eval"
    / "datasets"
    / "writer_verifier_gold_draft_v0.json"
)


class WriterVerifierEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        raw_dataset = DATASET_PATH.read_text(encoding="utf-8")
        self.dataset = WriterVerifierGoldDataset.model_validate_json(
            raw_dataset
        )

    def test_dataset_has_six_fixed_contract_behaviors(self) -> None:
        self.assertEqual(self.dataset.schema_version, "1")
        self.assertEqual(self.dataset.version, "0.1.0-draft")
        self.assertEqual(self.dataset.annotation_status, "draft")
        self.assertEqual(self.dataset.evidence_origin, "synthetic")
        self.assertEqual(
            self.dataset.evaluation_scope,
            "writer_verifier_fixed_contract",
        )
        self.assertEqual(len(self.dataset.cases), 6)
        self.assertEqual(
            {case.kind for case in self.dataset.cases},
            set(WriterVerifierCaseKind),
        )

    def test_writer_expectations_preserve_research_facts(self) -> None:
        for case in self.dataset.cases:
            results_by_id = {
                item.sub_question.id: item.result
                for item in case.writer_input.research_results
            }
            expectations_by_id = {
                item.sub_question_id: item
                for item in case.writer_expectations
            }
            self.assertEqual(set(expectations_by_id), set(results_by_id))
            for sub_question_id, result in results_by_id.items():
                expectation = expectations_by_id[sub_question_id]
                self.assertIs(
                    expectation.expected_evidence_status,
                    result.evidence_status,
                )
                self.assertEqual(
                    expectation.expected_evidence_reason,
                    result.evidence_reason,
                )
                self.assertEqual(
                    set(expectation.required_claim_ids),
                    {claim.id for claim in result.claims},
                )

    def test_gold_decisions_cover_pass_and_failure_types(self) -> None:
        cases_by_id = {case.case_id: case for case in self.dataset.cases}
        approved = {
            case_id
            for case_id, case in cases_by_id.items()
            if case.gold_verification.approved
        }
        self.assertEqual(
            approved,
            {
                "supported-single-source",
                "supported-multi-source-meg",
            },
        )
        expected_failures = {
            "invalid-provenance": VerificationIssueType.INVALID_PROVENANCE,
            "causal-upgrade": VerificationIssueType.CAUSAL_UPGRADE,
            "evidence-status-overstatement": (
                VerificationIssueType.EVIDENCE_STATUS_OVERSTATEMENT
            ),
            "targeted-localization": (
                VerificationIssueType.UNSUPPORTED_NUMBER
            ),
        }
        for case_id, issue_type in expected_failures.items():
            verification = cases_by_id[case_id].gold_verification
            self.assertFalse(verification.approved)
            self.assertEqual(
                {issue.type for issue in verification.issues},
                {issue_type},
            )

    def test_failure_localization_excludes_valid_sibling(self) -> None:
        case = next(
            item
            for item in self.dataset.cases
            if item.kind is WriterVerifierCaseKind.TARGETED_LOCALIZATION
        )
        self.assertEqual(
            case.gold_verification.failed_sub_question_ids,
            ["sq-decoding"],
        )
        self.assertNotIn(
            "sq-indexing",
            case.gold_verification.failed_sub_question_ids,
        )

    def test_real_verifier_runs_all_fixed_cases_safely(self) -> None:
        semantic_kinds = {
            WriterVerifierCaseKind.CAUSAL_UPGRADE,
            WriterVerifierCaseKind.TARGETED_LOCALIZATION,
        }
        for case in self.dataset.cases:
            with self.subTest(case=case.case_id):
                result = verify_report(
                    VerifierInput(
                        writer_input=case.writer_input,
                        report=case.candidate_report,
                    )
                )
                self.assertEqual(
                    result.approved,
                    case.gold_verification.approved,
                )
                self.assertEqual(
                    result.failed_sub_question_ids,
                    case.gold_verification.failed_sub_question_ids,
                )
                actual_types = {issue.type for issue in result.issues}
                gold_types = {
                    issue.type for issue in case.gold_verification.issues
                }
                if case.kind in semantic_kinds:
                    self.assertEqual(
                        actual_types,
                        {VerificationIssueType.UNSUPPORTED},
                    )
                else:
                    self.assertEqual(actual_types, gold_types)

    def test_dataset_rejects_boundary_and_localization_drift(self) -> None:
        raw_dataset = self.dataset.model_dump(mode="json")

        wrong_claims = deepcopy(raw_dataset)
        wrong_claims["cases"][0]["writer_expectations"][0][
            "required_claim_ids"
        ] = []
        with self.assertRaisesRegex(ValidationError, "exactly match"):
            WriterVerifierGoldDataset.model_validate(wrong_claims)

        wrong_statement = deepcopy(raw_dataset)
        wrong_statement["cases"][2]["gold_verification"]["issues"][0][
            "statement_id"
        ] = "missing-statement"
        with self.assertRaisesRegex(ValidationError, "must exist"):
            WriterVerifierGoldDataset.model_validate(wrong_statement)

        wrong_failed_id = deepcopy(raw_dataset)
        wrong_failed_id["cases"][2]["gold_verification"][
            "failed_sub_question_ids"
        ] = ["sq-unknown"]
        wrong_failed_id["cases"][2]["gold_verification"]["issues"][0][
            "sub_question_id"
        ] = "sq-unknown"
        with self.assertRaisesRegex(ValidationError, "reference research"):
            WriterVerifierGoldDataset.model_validate(wrong_failed_id)


if __name__ == "__main__":
    unittest.main()
