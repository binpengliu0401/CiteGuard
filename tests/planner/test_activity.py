import unittest
from unittest.mock import AsyncMock, patch

from temporalio.exceptions import ApplicationError

from citeguard.planner.activity import plan_research
from citeguard.planner.contracts import PlannerActivityInput
from citeguard.planner.schemas import DecomposedQuestion, DecompositionOutput


class PlannerActivityTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_memory_path_returns_domain_output(self) -> None:
        llm_output = DecompositionOutput(
            items=[
                DecomposedQuestion(
                    question="What is an AI agent?",
                    primary_answer_target="Definition of an AI agent",
                    answer_requirements=["The defining capabilities"],
                )
            ]
        )

        request_mock = AsyncMock(return_value=llm_output)
        with patch(
            "citeguard.planner.activity.request_structured_output",
            new=request_mock,
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
        self.assertEqual(
            result.sub_questions[0].answer_requirements[0].id,
            "req-001",
        )
        self.assertEqual(
            request_mock.await_args.kwargs["max_completion_tokens"],
            4_000,
        )

    async def test_memory_path_fails_explicitly(self) -> None:
        from citeguard.domain.research import (
            EvidenceGroup,
            EvidenceStatus,
            ResearchClaim,
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
                        claims=[
                            ResearchClaim(
                                id="claim-001",
                                statement="An agent is an autonomous system.",
                                source_ids=["2401.00001"],
                            )
                        ],
                        evidence_status=EvidenceStatus.SUPPORTED,
                        sources=[
                            ResearchSource(
                                title="Agent systems",
                                url="https://arxiv.org/abs/2401.00001",
                                source_id="2401.00001",
                                abstract="The paper defines agent systems.",
                                supported_aspects=(
                                    "The definition of agent systems."
                                ),
                                limitations=(
                                    "The paper covers one agent architecture."
                                ),
                            )
                        ],
                        evidence_group=EvidenceGroup(
                            source_ids=["2401.00001"]
                        ),
                    ),
                )
            ],
        )

        with self.assertRaises(ApplicationError):
            await plan_research(planner_input)


if __name__ == "__main__":
    unittest.main()
