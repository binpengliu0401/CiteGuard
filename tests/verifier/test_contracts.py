"""Verify durable Verifier input and serialization boundaries."""

import unittest

from citeguard.domain.report import (
    ReportSection,
    ReportStatement,
    VerificationResult,
    WrittenReport,
)
from citeguard.domain.research import EvidenceStatus
from citeguard.infrastructure.temporal import TEMPORAL_DATA_CONVERTER
from citeguard.verifier.contracts import VerifierInput
from citeguard.writer.contracts import WriterInput
from tests.writer.test_contracts import completed_research


class VerifierInputTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _writer_input() -> WriterInput:
        return WriterInput(
            research_question="Does retrieval improve factual accuracy?",
            research_results=[completed_research()],
        )

    @staticmethod
    def _report() -> WrittenReport:
        return WrittenReport(
            research_question="Does retrieval improve factual accuracy?",
            sections=[
                ReportSection(
                    sub_question_id="sq-001",
                    evidence_status=EvidenceStatus.SUPPORTED,
                    statements=[
                        ReportStatement(
                            id="stmt-001",
                            text="Retrieval improved factual accuracy.",
                            sub_question_id="sq-001",
                            claim_ids=["claim-001"],
                            source_ids=["2401.00001"],
                        )
                    ],
                )
            ],
        )

    def test_requires_matching_original_question(self) -> None:
        report = self._report()
        mismatched_input = WriterInput(
            research_question="A different question?",
            research_results=[completed_research()],
        )

        with self.assertRaisesRegex(ValueError, "must match"):
            VerifierInput(
                writer_input=mismatched_input,
                report=report,
            )

    async def test_temporal_converter_round_trips_boundaries(self) -> None:
        verifier_input = VerifierInput(
            writer_input=self._writer_input(),
            report=self._report(),
        )
        approved = VerificationResult(
            approved=True,
            issues=[],
            failed_sub_question_ids=[],
        )

        payloads = await TEMPORAL_DATA_CONVERTER.encode(
            [verifier_input, approved]
        )
        decoded = await TEMPORAL_DATA_CONVERTER.decode(
            payloads,
            [VerifierInput, VerificationResult],
        )

        self.assertEqual(decoded, [verifier_input, approved])


if __name__ == "__main__":
    unittest.main()
