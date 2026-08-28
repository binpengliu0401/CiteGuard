"""Verify the formal Workflow's durable input and result contracts."""

import unittest

from citeguard.infrastructure.temporal import TEMPORAL_DATA_CONVERTER
from citeguard.verifier.contracts import VerifierInput
from citeguard.verifier.verification import verify_report
from citeguard.writer.assembly import assemble_report
from citeguard.writer.contracts import WriterInput
from citeguard.workflows.contracts import (
    CiteGuardWorkflowInput,
    CiteGuardWorkflowResult,
)
from tests.writer.helpers import supported_item


class WorkflowContractTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _result() -> CiteGuardWorkflowResult:
        item = supported_item("sq-001", "claim-001", "source-001")
        writer_input = WriterInput(
            research_question="What is the supported finding?",
            research_results=[item],
        )
        report = assemble_report(writer_input)
        verification = verify_report(
            VerifierInput(writer_input=writer_input, report=report)
        )
        return CiteGuardWorkflowResult(
            sub_question=item.sub_question,
            research_result=item.result,
            report=report,
            verification=verification,
        )

    def test_input_rejects_blank_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "session_id"):
            CiteGuardWorkflowInput(
                research_question="What is the finding?",
                session_id=" ",
            )

    def test_result_rejects_untyped_pipeline_stage(self) -> None:
        result = self._result()

        with self.assertRaisesRegex(TypeError, "research_result"):
            CiteGuardWorkflowResult(
                sub_question=result.sub_question,
                research_result=object(),  # type: ignore[arg-type]
                report=result.report,
                verification=result.verification,
            )

    async def test_temporal_converter_round_trips_workflow_boundary(
        self,
    ) -> None:
        workflow_input = CiteGuardWorkflowInput(
            research_question="What is the supported finding?",
            session_id="session-001",
        )
        result = self._result()

        payloads = await TEMPORAL_DATA_CONVERTER.encode(
            [workflow_input, result]
        )
        decoded = await TEMPORAL_DATA_CONVERTER.decode(
            payloads,
            [CiteGuardWorkflowInput, CiteGuardWorkflowResult],
        )

        self.assertEqual(decoded, [workflow_input, result])


if __name__ == "__main__":
    unittest.main()
