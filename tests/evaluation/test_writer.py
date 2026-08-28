"""Verify Writer Gold coverage and deterministic hard gates."""

import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from pydantic import ValidationError

from citeguard.domain.report import (
    ReportStatement,
    WrittenReport,
)
from citeguard.domain.research import (
    EvidenceStatus,
    SubQuestionStatus,
)
from citeguard.evaluation.writer import (
    WriterCaseKind,
    WriterFailureType,
    WriterGoldCase,
    WriterGoldDataset,
    evaluate_writer_report,
)
from citeguard.writer.assembly import assemble_report

PROJECT_ROOT = Path(__file__).parents[2]
DATASET_PATH = (
    PROJECT_ROOT / "eval" / "datasets" / "writer_gold_draft_v0.json"
)


class WriterGoldTests(unittest.TestCase):
    def setUp(self) -> None:
        raw_dataset = DATASET_PATH.read_text(encoding="utf-8")
        self.dataset = WriterGoldDataset.model_validate_json(raw_dataset)
        self.cases_by_kind = {
            case.kind: case for case in self.dataset.cases
        }

    def test_six_cases_cover_the_writer_v0_boundary(self) -> None:
        self.assertEqual(self.dataset.schema_version, "1")
        self.assertEqual(self.dataset.version, "0.1.0-draft")
        self.assertEqual(self.dataset.annotation_status, "draft")
        self.assertEqual(self.dataset.evidence_origin, "synthetic")
        self.assertEqual(len(self.dataset.cases), 6)
        self.assertEqual(
            set(self.cases_by_kind),
            set(WriterCaseKind),
        )

        results = [
            item
            for case in self.dataset.cases
            for item in case.writer_input.research_results
        ]
        self.assertEqual(
            {item.result.evidence_status for item in results},
            set(EvidenceStatus),
        )
        self.assertEqual(
            {item.sub_question.status for item in results},
            set(SubQuestionStatus),
        )
        claim_counts = {len(item.result.claims) for item in results}
        self.assertTrue({0, 1}.issubset(claim_counts))
        self.assertTrue(any(count > 1 for count in claim_counts))
        self.assertTrue(
            any(
                len(claim.source_ids) > 1
                for item in results
                for claim in item.result.claims
            )
        )
        self.assertTrue(
            any(len(case.gold_sections) > 1 for case in self.dataset.cases)
        )

    def test_valid_reports_pass_every_hard_gate(self) -> None:
        for case in self.dataset.cases:
            with self.subTest(case=case.case_id):
                result = evaluate_writer_report(
                    case,
                    assemble_report(case.writer_input),
                )
                self.assertTrue(result.passed)
                self.assertEqual(result.failures, [])
                self.assertEqual(result.metrics.section_coverage, 1.0)
                self.assertEqual(result.metrics.claim_recall, 1.0)
                self.assertEqual(result.metrics.provenance_precision, 1.0)
                self.assertEqual(result.metrics.provenance_recall, 1.0)
                self.assertEqual(
                    result.metrics.evidence_status_accuracy,
                    1.0,
                )
                self.assertEqual(
                    result.metrics.evidence_reason_accuracy,
                    1.0,
                )

    def test_gold_rejects_provenance_order_and_kind_drift(self) -> None:
        raw_dataset = self.dataset.model_dump(mode="json")

        wrong_source = deepcopy(raw_dataset)
        wrong_source["cases"][0]["gold_sections"][0]["claims"][0][
            "source_ids"
        ] = ["source-unknown"]
        with self.assertRaisesRegex(ValidationError, "must match research"):
            WriterGoldDataset.model_validate(wrong_source)

        wrong_order = deepcopy(raw_dataset)
        wrong_order["cases"][5]["gold_sections"].reverse()
        with self.assertRaisesRegex(ValidationError, "input order"):
            WriterGoldDataset.model_validate(wrong_order)

        missing_kind = deepcopy(raw_dataset)
        missing_kind["cases"].pop()
        with self.assertRaisesRegex(ValidationError, "every v0 case kind"):
            WriterGoldDataset.model_validate(missing_kind)

    def test_merged_claims_do_not_hide_cross_provenance(self) -> None:
        case = self.cases_by_kind[
            WriterCaseKind.SUPPORTED_MULTI_CLAIM_MEG
        ]
        report = assemble_report(case.writer_input)
        merged = ReportStatement(
            id="statement-merged",
            text="Reranking and citation checks improved grounding.",
            sub_question_id="sq-multi",
            claim_ids=["claim-reranking", "claim-citation"],
            source_ids=["source-reranking", "source-citation"],
        )
        changed = self._replace_first_section(
            report,
            statements=[merged],
        )

        result = evaluate_writer_report(case, changed)

        self.assertFalse(result.passed)
        self.assertIn(
            WriterFailureType.INVALID_PROVENANCE,
            {failure.type for failure in result.failures},
        )
        self.assertEqual(result.metrics.provenance_precision, 0.5)

    def test_claim_ids_are_scoped_by_subquestion(self) -> None:
        original = self.cases_by_kind[
            WriterCaseKind.MIXED_NEW_AND_REUSED
        ]
        raw_case = original.model_dump(mode="json")
        research_results = raw_case["writer_input"]["research_results"]
        research_results[0]["result"]["claims"][0]["id"] = "claim-001"
        research_results[1]["result"]["claims"][0]["id"] = "claim-001"
        reused_result = research_results[1]["sub_question"][
            "reused_result"
        ]
        reused_result["claims"][0]["id"] = "claim-001"
        raw_case["gold_sections"][0]["claims"][0][
            "claim_id"
        ] = "claim-001"
        raw_case["gold_sections"][1]["claims"][0][
            "claim_id"
        ] = "claim-001"
        case = WriterGoldCase.model_validate(raw_case)

        result = evaluate_writer_report(
            case,
            assemble_report(case.writer_input),
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.metrics.provenance_recall, 1.0)

    def test_mutations_exercise_every_writer_failure_type(self) -> None:
        mutations = self._failure_mutations()
        self.assertEqual(
            {failure_type for failure_type, _, _ in mutations},
            set(WriterFailureType),
        )
        for failure_type, case, report in mutations:
            with self.subTest(failure_type=failure_type.value):
                result = evaluate_writer_report(case, report)
                self.assertFalse(result.passed)
                self.assertIn(
                    failure_type,
                    {failure.type for failure in result.failures},
                )

    def _failure_mutations(
        self,
    ) -> list[tuple[WriterFailureType, WriterGoldCase, WrittenReport]]:
        single = self.cases_by_kind[
            WriterCaseKind.SUPPORTED_SINGLE_SOURCE
        ]
        multi = self.cases_by_kind[
            WriterCaseKind.SUPPORTED_MULTI_CLAIM_MEG
        ]
        joint = self.cases_by_kind[
            WriterCaseKind.SUPPORTED_JOINT_SOURCE_CLAIM
        ]
        partial = self.cases_by_kind[
            WriterCaseKind.INSUFFICIENT_PARTIAL_EVIDENCE
        ]
        empty = self.cases_by_kind[WriterCaseKind.NO_RELEVANT_SOURCES]
        mixed = self.cases_by_kind[WriterCaseKind.MIXED_NEW_AND_REUSED]

        single_report = assemble_report(single.writer_input)
        multi_report = assemble_report(multi.writer_input)
        joint_report = assemble_report(joint.writer_input)
        partial_report = assemble_report(partial.writer_input)
        empty_report = assemble_report(empty.writer_input)
        mixed_report = assemble_report(mixed.writer_input)

        unknown_claim = replace(
            single_report.sections[0].statements[0],
            claim_ids=["claim-unknown"],
        )
        unknown_source = replace(
            single_report.sections[0].statements[0],
            source_ids=["source-unknown"],
        )
        wrong_source = replace(
            multi_report.sections[0].statements[0],
            source_ids=["source-citation"],
        )
        wrong_scope = replace(
            mixed_report.sections[0].statements[0],
            claim_ids=["claim-reused"],
            source_ids=["source-reused"],
        )
        unexpected = ReportStatement(
            id="statement-unexpected",
            text="A polar-region evaluation was found.",
            sub_question_id="sq-none",
            claim_ids=["claim-invented"],
            source_ids=["source-invented"],
        )
        return [
            (
                WriterFailureType.RESEARCH_QUESTION_MISMATCH,
                single,
                replace(single_report, research_question="Wrong question"),
            ),
            (
                WriterFailureType.SECTION_COVERAGE,
                mixed,
                replace(mixed_report, sections=mixed_report.sections[:1]),
            ),
            (
                WriterFailureType.SECTION_ORDER,
                mixed,
                replace(
                    mixed_report,
                    sections=list(reversed(mixed_report.sections)),
                ),
            ),
            (
                WriterFailureType.EVIDENCE_STATUS,
                partial,
                self._replace_first_section(
                    partial_report,
                    evidence_status=EvidenceStatus.SUPPORTED,
                ),
            ),
            (
                WriterFailureType.EVIDENCE_REASON,
                partial,
                self._replace_first_section(
                    partial_report,
                    evidence_reason="A different reason.",
                ),
            ),
            (
                WriterFailureType.MISSING_CLAIM,
                multi,
                self._replace_first_section(
                    multi_report,
                    statements=multi_report.sections[0].statements[:1],
                ),
            ),
            (
                WriterFailureType.UNKNOWN_CLAIM,
                single,
                self._replace_first_section(
                    single_report,
                    statements=[unknown_claim],
                ),
            ),
            (
                WriterFailureType.CLAIM_SCOPE,
                mixed,
                self._replace_first_section(
                    mixed_report,
                    statements=[wrong_scope],
                ),
            ),
            (
                WriterFailureType.MISSING_SOURCE,
                joint,
                self._replace_first_section(
                    joint_report,
                    statements=[
                        replace(
                            joint_report.sections[0].statements[0],
                            source_ids=["source-joint-a"],
                        )
                    ],
                ),
            ),
            (
                WriterFailureType.UNKNOWN_SOURCE,
                single,
                self._replace_first_section(
                    single_report,
                    statements=[unknown_source],
                ),
            ),
            (
                WriterFailureType.INVALID_PROVENANCE,
                multi,
                self._replace_first_section(
                    multi_report,
                    statements=[
                        wrong_source,
                        multi_report.sections[0].statements[1],
                    ],
                ),
            ),
            (
                WriterFailureType.UNEXPECTED_STATEMENT,
                empty,
                self._replace_first_section(
                    empty_report,
                    statements=[unexpected],
                ),
            ),
        ]

    @staticmethod
    def _replace_first_section(
        report: WrittenReport,
        **updates: object,
    ) -> WrittenReport:
        changed = replace(report.sections[0], **updates)
        return replace(report, sections=[changed, *report.sections[1:]])


if __name__ == "__main__":
    unittest.main()
