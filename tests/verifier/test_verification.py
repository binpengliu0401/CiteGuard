"""Verify deterministic Verifier provenance and evidence-state gates."""

import unittest
from dataclasses import replace

from citeguard.domain.report import (
    VerificationIssueType,
    WrittenReport,
)
from citeguard.domain.research import EvidenceStatus
from citeguard.verifier.contracts import VerifierInput
from citeguard.verifier.verification import verify_report
from citeguard.writer.assembly import assemble_report
from citeguard.writer.contracts import WriterInput
from tests.writer.helpers import (
    insufficient_item,
    no_relevant_item,
    supported_item,
)


class VerifierTests(unittest.TestCase):
    def test_approves_exact_supported_partial_and_empty_sections(self) -> None:
        writer_input = WriterInput(
            research_question="Summarize the available evidence.",
            research_results=[
                supported_item("sq-supported", "claim-001", "source-a"),
                insufficient_item("sq-partial"),
                no_relevant_item("sq-empty"),
            ],
        )

        result = verify_report(
            VerifierInput(
                writer_input=writer_input,
                report=assemble_report(writer_input),
            )
        )

        self.assertTrue(result.approved)
        self.assertEqual(result.issues, [])
        self.assertEqual(result.failed_sub_question_ids, [])

    def test_rejects_wrong_claim_source_edge(self) -> None:
        writer_input = self._two_supported_inputs()
        report = assemble_report(writer_input)
        first_statement = replace(
            report.sections[0].statements[0],
            source_ids=["source-b"],
        )
        first_section = replace(
            report.sections[0],
            statements=[first_statement],
        )
        changed = replace(
            report,
            sections=[first_section, report.sections[1]],
        )

        result = verify_report(
            VerifierInput(writer_input=writer_input, report=changed)
        )

        self.assertFalse(result.approved)
        self.assertEqual(result.failed_sub_question_ids, ["sq-a"])
        self.assertEqual(
            {issue.type for issue in result.issues},
            {VerificationIssueType.INVALID_PROVENANCE},
        )
        self.assertEqual(result.issues[0].statement_id, "statement-001")

    def test_rejects_unknown_claim_and_source_ids(self) -> None:
        writer_input = WriterInput(
            research_question="What is the supported finding?",
            research_results=[
                supported_item("sq-001", "claim-001", "source-001")
            ],
        )
        report = assemble_report(writer_input)
        changed_statement = replace(
            report.sections[0].statements[0],
            claim_ids=["claim-unknown"],
            source_ids=["source-unknown"],
        )
        changed = self._replace_first_section(
            report,
            statements=[changed_statement],
        )

        result = verify_report(
            VerifierInput(writer_input=writer_input, report=changed)
        )

        issue_types = {issue.type for issue in result.issues}
        self.assertIn(VerificationIssueType.UNKNOWN_CLAIM, issue_types)
        self.assertIn(VerificationIssueType.UNKNOWN_SOURCE, issue_types)
        self.assertIn(VerificationIssueType.MISSING_PROVENANCE, issue_types)
        self.assertEqual(result.failed_sub_question_ids, ["sq-001"])

    def test_rejects_evidence_status_overstatement(self) -> None:
        writer_input = WriterInput(
            research_question="Is the evidence complete?",
            research_results=[insufficient_item("sq-partial")],
        )
        report = assemble_report(writer_input)
        changed = self._replace_first_section(
            report,
            evidence_status=EvidenceStatus.SUPPORTED,
            evidence_reason=None,
        )

        result = verify_report(
            VerifierInput(writer_input=writer_input, report=changed)
        )

        self.assertEqual(len(result.issues), 1)
        self.assertIs(
            result.issues[0].type,
            VerificationIssueType.EVIDENCE_STATUS_OVERSTATEMENT,
        )
        self.assertEqual(result.failed_sub_question_ids, ["sq-partial"])

    def test_nonexact_text_is_safely_rejected_as_unsupported(self) -> None:
        writer_input = WriterInput(
            research_question="What relation did the study find?",
            research_results=[
                supported_item("sq-relation", "claim-001", "source-001")
            ],
        )
        report = assemble_report(writer_input)
        changed_statement = replace(
            report.sections[0].statements[0],
            text="The intervention caused the outcome.",
        )
        changed = self._replace_first_section(
            report,
            statements=[changed_statement],
        )

        result = verify_report(
            VerifierInput(writer_input=writer_input, report=changed)
        )

        self.assertEqual(
            {issue.type for issue in result.issues},
            {VerificationIssueType.UNSUPPORTED},
        )
        self.assertEqual(result.failed_sub_question_ids, ["sq-relation"])

    def test_only_the_invalid_sibling_is_selected(self) -> None:
        writer_input = self._two_supported_inputs()
        report = assemble_report(writer_input)
        changed_statement = replace(
            report.sections[1].statements[0],
            text="An unsupported numeric claim.",
        )
        second_section = replace(
            report.sections[1],
            statements=[changed_statement],
        )
        changed = replace(
            report,
            sections=[report.sections[0], second_section],
        )

        result = verify_report(
            VerifierInput(writer_input=writer_input, report=changed)
        )

        self.assertEqual(result.failed_sub_question_ids, ["sq-b"])
        self.assertTrue(
            all(issue.sub_question_id == "sq-b" for issue in result.issues)
        )

    def test_missing_section_and_claim_are_localized(self) -> None:
        writer_input = self._two_supported_inputs()
        report = assemble_report(writer_input)
        missing_section = replace(report, sections=report.sections[:1])
        missing_claim = self._replace_first_section(
            report,
            statements=[],
        )

        section_result = verify_report(
            VerifierInput(
                writer_input=writer_input,
                report=missing_section,
            )
        )
        claim_result = verify_report(
            VerifierInput(
                writer_input=writer_input,
                report=missing_claim,
            )
        )

        self.assertEqual(section_result.failed_sub_question_ids, ["sq-b"])
        self.assertEqual(claim_result.failed_sub_question_ids, ["sq-a"])
        self.assertTrue(
            all(
                issue.type is VerificationIssueType.MISSING_PROVENANCE
                for issue in [
                    *section_result.issues,
                    *claim_result.issues,
                ]
            )
        )

    @staticmethod
    def _two_supported_inputs() -> WriterInput:
        return WriterInput(
            research_question="Compare two supported findings.",
            research_results=[
                supported_item("sq-a", "claim-001", "source-a"),
                supported_item("sq-b", "claim-001", "source-b"),
            ],
        )

    @staticmethod
    def _replace_first_section(
        report: WrittenReport,
        **updates: object,
    ) -> WrittenReport:
        first_section = replace(report.sections[0], **updates)
        return replace(
            report,
            sections=[first_section, *report.sections[1:]],
        )


if __name__ == "__main__":
    unittest.main()
