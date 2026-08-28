"""Verify deterministic orchestration and minimal-pipeline terminal states."""

import unittest
from collections.abc import Callable
from unittest.mock import patch

from temporalio.exceptions import ApplicationError

from citeguard.domain.report import (
    ReportSection,
    ReportStatement,
    WrittenReport,
)
from citeguard.planner.contracts import PlannerActivityOutput
from citeguard.verifier.contracts import VerifierInput
from citeguard.verifier.verification import verify_report
from citeguard.writer.assembly import assemble_report
from citeguard.writer.contracts import WriterInput
from citeguard.workflows.citeguard_workflow import CiteGuardWorkflow
from citeguard.workflows.contracts import CiteGuardWorkflowInput
from tests.writer.helpers import no_relevant_item, supported_item


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    workflow_input = CiteGuardWorkflowInput(
        research_question="What is the supported finding?",
        session_id="session-001",
    )

    async def _run_with(
        self,
        execute_activity: Callable[..., object],
    ):
        with patch(
            "citeguard.workflows.citeguard_workflow."
            "workflow.execute_activity",
            new=execute_activity,
        ):
            return await CiteGuardWorkflow().run(self.workflow_input)

    async def test_runs_all_four_stages_and_returns_approval(self) -> None:
        item = supported_item("sq-001", "claim-001", "source-001")
        calls: list[tuple[str, object, dict[str, object]]] = []

        async def execute(
            name: str,
            argument: object,
            **kwargs: object,
        ) -> object:
            calls.append((name, argument, kwargs))
            if name == "plan_research":
                return PlannerActivityOutput(
                    sub_questions=[item.sub_question]
                )
            if name == "research_sub_question":
                return item.result
            if name == "write_report":
                return assemble_report(argument)  # type: ignore[arg-type]
            return verify_report(argument)  # type: ignore[arg-type]

        result = await self._run_with(execute)

        self.assertTrue(result.verification.approved)
        self.assertEqual(
            [name for name, _, _ in calls],
            [
                "plan_research",
                "research_sub_question",
                "write_report",
                "verify_report",
            ],
        )
        self.assertIsInstance(calls[2][1], WriterInput)
        self.assertIsInstance(calls[3][1], VerifierInput)
        self.assertEqual(
            [call[2]["retry_policy"].maximum_attempts for call in calls],
            [3, 3, 1, 1],
        )

    async def test_source_free_result_completes_and_is_approved(self) -> None:
        item = no_relevant_item("sq-001")

        async def execute(
            name: str,
            argument: object,
            **_: object,
        ) -> object:
            if name == "plan_research":
                return PlannerActivityOutput(
                    sub_questions=[item.sub_question]
                )
            if name == "research_sub_question":
                return item.result
            if name == "write_report":
                return assemble_report(argument)  # type: ignore[arg-type]
            return verify_report(argument)  # type: ignore[arg-type]

        result = await self._run_with(execute)

        self.assertTrue(result.verification.approved)
        self.assertEqual(result.report.sections[0].statements, [])
        self.assertEqual(
            result.report.sections[0].evidence_reason,
            "No relevant abstract was found.",
        )

    async def test_verifier_rejection_is_returned_normally(self) -> None:
        item = supported_item("sq-001", "claim-001", "source-001")

        async def execute(
            name: str,
            argument: object,
            **_: object,
        ) -> object:
            if name == "plan_research":
                return PlannerActivityOutput(
                    sub_questions=[item.sub_question]
                )
            if name == "research_sub_question":
                return item.result
            if name == "write_report":
                original = assemble_report(argument)  # type: ignore[arg-type]
                statement = original.sections[0].statements[0]
                return WrittenReport(
                    research_question=original.research_question,
                    sections=[
                        ReportSection(
                            sub_question_id="sq-001",
                            evidence_status=item.result.evidence_status,
                            statements=[
                                ReportStatement(
                                    id=statement.id,
                                    text="An unsupported changed finding.",
                                    sub_question_id="sq-001",
                                    claim_ids=list(statement.claim_ids),
                                    source_ids=list(statement.source_ids),
                                )
                            ],
                        )
                    ],
                    limitations=list(original.limitations),
                )
            return verify_report(argument)  # type: ignore[arg-type]

        result = await self._run_with(execute)

        self.assertFalse(result.verification.approved)
        self.assertEqual(
            result.verification.failed_sub_question_ids,
            ["sq-001"],
        )
        self.assertEqual(
            result.verification.issues[0].type.value,
            "unsupported",
        )

    async def test_multiple_subquestions_fail_before_research(self) -> None:
        first = supported_item("sq-001", "claim-001", "source-001")
        second = supported_item("sq-002", "claim-002", "source-002")
        calls: list[str] = []

        async def execute(
            name: str,
            _: object,
            **__: object,
        ) -> object:
            calls.append(name)
            return PlannerActivityOutput(
                sub_questions=[first.sub_question, second.sub_question]
            )

        with self.assertRaises(ApplicationError) as raised:
            await self._run_with(execute)

        self.assertEqual(calls, ["plan_research"])
        self.assertTrue(raised.exception.non_retryable)
        self.assertEqual(
            raised.exception.type,
            "SingleResearcherLimitExceeded",
        )

    async def test_activity_failure_propagates_to_workflow(self) -> None:
        item = supported_item("sq-001", "claim-001", "source-001")

        async def execute(
            name: str,
            _: object,
            **__: object,
        ) -> object:
            if name == "plan_research":
                return PlannerActivityOutput(
                    sub_questions=[item.sub_question]
                )
            raise ApplicationError(
                "Research failed permanently.",
                type="InvalidResearcherResult",
                non_retryable=True,
            )

        with self.assertRaises(ApplicationError) as raised:
            await self._run_with(execute)

        self.assertEqual(
            raised.exception.type,
            "InvalidResearcherResult",
        )


if __name__ == "__main__":
    unittest.main()
