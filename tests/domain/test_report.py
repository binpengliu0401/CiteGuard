"""Verify shared report and verification-domain invariants."""

import unittest

from citeguard.domain.report import (
    ReportSection,
    ReportStatement,
    VerificationIssue,
    VerificationIssueType,
    VerificationResult,
    WrittenReport,
)
from citeguard.domain.research import EvidenceStatus


class ReportDomainTests(unittest.TestCase):
    @staticmethod
    def _statement() -> ReportStatement:
        return ReportStatement(
            id="stmt-001",
            text="Retrieval reduced the reported hallucination rate.",
            sub_question_id="sq-001",
            claim_ids=["claim-001"],
            source_ids=["2401.00001"],
        )

    def test_report_preserves_statement_provenance(self) -> None:
        section = ReportSection(
            sub_question_id="sq-001",
            evidence_status=EvidenceStatus.SUPPORTED,
            statements=[self._statement()],
        )
        report = WrittenReport(
            research_question="Does retrieval improve factuality?",
            sections=[section],
        )

        statement = report.sections[0].statements[0]
        self.assertEqual(statement.claim_ids, ["claim-001"])
        self.assertEqual(statement.source_ids, ["2401.00001"])

        with self.assertRaisesRegex(TypeError, "must be a list"):
            WrittenReport(
                research_question="Does retrieval improve factuality?",
                sections=(section,),  # type: ignore[arg-type]
            )

    def test_statement_requires_explicit_provenance(self) -> None:
        with self.assertRaisesRegex(ValueError, "claim_ids"):
            ReportStatement(
                id="stmt-001",
                text="An unsupported statement.",
                sub_question_id="sq-001",
                claim_ids=[],
                source_ids=["2401.00001"],
            )

    def test_report_statement_ids_are_globally_unique(self) -> None:
        second = ReportStatement(
            id="stmt-001",
            text="A second statement with a duplicate ID.",
            sub_question_id="sq-002",
            claim_ids=["claim-001"],
            source_ids=["2402.00002"],
        )

        with self.assertRaisesRegex(ValueError, "globally unique"):
            WrittenReport(
                research_question="Compare two findings.",
                sections=[
                    ReportSection(
                        sub_question_id="sq-001",
                        evidence_status=EvidenceStatus.SUPPORTED,
                        statements=[self._statement()],
                    ),
                    ReportSection(
                        sub_question_id="sq-002",
                        evidence_status=EvidenceStatus.SUPPORTED,
                        statements=[second],
                    ),
                ],
            )

    def test_approved_result_has_no_failures(self) -> None:
        result = VerificationResult(
            approved=True,
            issues=[],
            failed_sub_question_ids=[],
        )

        self.assertTrue(result.approved)

        with self.assertRaisesRegex(ValueError, "must not contain"):
            VerificationResult(
                approved=True,
                issues=[
                    VerificationIssue(
                        type=VerificationIssueType.UNSUPPORTED,
                        sub_question_id="sq-001",
                        statement_id="stmt-001",
                        reason="The abstract does not support the statement.",
                    )
                ],
                failed_sub_question_ids=["sq-001"],
            )

    def test_rejected_result_has_exact_issue_scope(self) -> None:
        issue = VerificationIssue(
            type=VerificationIssueType.INVALID_PROVENANCE,
            sub_question_id="sq-001",
            statement_id="stmt-001",
            claim_ids=["claim-001"],
            source_ids=["2401.00001"],
            reason="The source is not bound to the cited claim.",
        )
        result = VerificationResult(
            approved=False,
            issues=[issue],
            failed_sub_question_ids=["sq-001"],
        )

        self.assertEqual(result.failed_sub_question_ids, ["sq-001"])

        with self.assertRaisesRegex(ValueError, "exactly match"):
            VerificationResult(
                approved=False,
                issues=[issue],
                failed_sub_question_ids=["sq-002"],
            )


if __name__ == "__main__":
    unittest.main()
