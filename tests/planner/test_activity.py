import unittest
from unittest.mock import AsyncMock, patch

from temporalio.exceptions import ApplicationError

from citeguard.planner.activity import plan_research
from citeguard.planner.contracts import PlannerActivityInput
from citeguard.planner.schemas import DecomposedQuestion, DecompositionOutput


class PlannerActivityTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_memory_path_returns_domain_output(self) -> None:
        llm_output = DecompositionOutput(
            items=[DecomposedQuestion(question="What is an AI agent?")]
        )

        with patch(
            "citeguard.planner.activity.request_structured_output",
            new=AsyncMock(return_value=llm_output),
        ):
            result = await plan_research(
                PlannerActivityInput(
                    research_question="What is an AI agent?",
                    session_id="session-1",
                    existing_notes=[],
                )
            )

        self.assertEqual(result.sub_questions[0].id, "sq-001")
        self.assertEqual(
            result.sub_questions[0].question,
            "What is an AI agent?",
        )

    async def test_memory_path_fails_explicitly(self) -> None:
        from citeguard.domain.research import (
            EvidenceStatus,
            ResearchNote,
            ResearchResult,
            ResearchSource,
        )

        planner_input = PlannerActivityInput(
            research_question="What is an AI agent?",
            session_id="session-1",
            existing_notes=[
                ResearchNote(
                    id="note-1",
                    question="What is an AI agent?",
                    result=ResearchResult(
                        answer="An autonomous tool-using system.",
                        evidence_status=EvidenceStatus.SUPPORTED,
                        sources=[
                            ResearchSource(
                                title="Agent systems",
                                url="https://arxiv.org/abs/2401.00001",
                                supported_aspects=(
                                    "The definition of agent systems."
                                ),
                                limitations=(
                                    "The paper covers one agent architecture."
                                ),
                                source_id="2401.00001",
                            )
                        ],
                    ),
                )
            ],
        )

        with self.assertRaises(ApplicationError):
            await plan_research(planner_input)


if __name__ == "__main__":
    unittest.main()
