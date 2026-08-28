"""Verify the deterministic Verifier Temporal Activity."""

import unittest

from temporalio.exceptions import ApplicationError

from citeguard.domain.report import (
    ReportSection,
    ReportStatement,
    WrittenReport,
)
from citeguard.domain.research import EvidenceStatus
from citeguard.verifier.activity import verify_written_report
from citeguard.verifier.contracts import VerifierInput
from citeguard.writer.assembly import assemble_report
from citeguard.writer.contracts import WriterInput
from tests.writer.helpers import supported_item


class VerifierActivityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.writer_input = WriterInput(
            research_question="What is the supported finding?",
            research_results=[
                supported_item("sq-001", "claim-001", "source-001")
            ],
        )

    async def test_content_failure_is_a_normal_result(self) -> None:
        report = assemble_report(self.writer_input)
        unsupported = WrittenReport(
            research_question=report.research_question,
            sections=[
                ReportSection(
                    sub_question_id="sq-001",
                    evidence_status=EvidenceStatus.SUPPORTED,
                    statements=[
                        ReportStatement(
                            id="statement-001",
                            text="A changed claim.",
                            sub_question_id="sq-001",
                            claim_ids=["claim-001"],
                            source_ids=["source-001"],
                        )
                    ],
                )
            ],
        )

        result = await verify_written_report(
            VerifierInput(
                writer_input=self.writer_input,
                report=unsupported,
            )
        )

        self.assertFalse(result.approved)
        self.assertEqual(result.failed_sub_question_ids, ["sq-001"])

    async def test_unmappable_section_is_nonretryable(self) -> None:
        report = WrittenReport(
            research_question=self.writer_input.research_question,
            sections=[
                ReportSection(
                    sub_question_id="sq-unknown",
                    evidence_status=EvidenceStatus.SUPPORTED,
                    statements=[
                        ReportStatement(
                            id="statement-unknown",
                            text="An unknown section claim.",
                            sub_question_id="sq-unknown",
                            claim_ids=["claim-unknown"],
                            source_ids=["source-unknown"],
                        )
                    ],
                )
            ],
        )

        with self.assertRaises(ApplicationError) as raised:
            await verify_written_report(
                VerifierInput(
                    writer_input=self.writer_input,
                    report=report,
                )
            )

        self.assertTrue(raised.exception.non_retryable)
        self.assertEqual(raised.exception.type, "InvalidVerifierReport")


if __name__ == "__main__":
    unittest.main()
