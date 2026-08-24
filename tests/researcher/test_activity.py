"""Verify the Researcher Activity sequence and capability gates."""

import unittest
from unittest.mock import AsyncMock, patch

from temporalio.exceptions import ApplicationError

from citeguard.domain.research import (
    EvidenceStatus,
    ResearchResult,
    SubQuestion,
    SubQuestionStatus,
)
from citeguard.researcher.activity import (
    SYNTHESIS_MAX_COMPLETION_TOKENS,
    research_sub_question,
)
from citeguard.researcher.arxiv import ArxivPaper
from citeguard.researcher.contracts import ResearchTaskInput
from citeguard.researcher.schemas import (
    PaperAssessment,
    RelevanceLevel,
    ResearchSynthesisOutput,
    SearchPlanOutput,
)


class ResearcherActivityTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _task(status: SubQuestionStatus = SubQuestionStatus.NEW) -> ResearchTaskInput:
        reused_result = None
        source_note_id = None
        if status is SubQuestionStatus.REUSED_FROM_MEMORY:
            reused_result = ResearchResult(
                answer="A previous answer.",
                evidence_status=EvidenceStatus.NO_RELEVANT_SOURCES,
                evidence_reason="The previous search found no relevant sources.",
            )
            source_note_id = "note-001"
        return ResearchTaskInput(
            sub_question=SubQuestion(
                id="sq-001",
                question="Does retrieval improve factuality?",
                status=status,
                reused_result=reused_result,
                source_note_id=source_note_id,
            )
        )

    @staticmethod
    def _paper() -> ArxivPaper:
        return ArxivPaper(
            title="Retrieval and factuality",
            source_id="2401.00001",
            summary="We report improved factuality in a controlled evaluation.",
            url="https://arxiv.org/abs/2401.00001",
        )

    async def test_executes_exactly_two_llm_calls_and_one_mcp_search(self) -> None:
        synthesis = ResearchSynthesisOutput(
            answer="Retrieval improved factuality in the reported evaluation.",
            evidence_status=EvidenceStatus.SUPPORTED,
            evidence_reason=None,
            used_source_ids=["2401.00001"],
            assessments=[
                PaperAssessment(
                    source_id="2401.00001",
                    relevance=RelevanceLevel.DIRECT,
                    supported_aspects="The retrieval method and factuality outcome.",
                    limitations="The abstract does not expose all measurements.",
                )
            ],
        )
        llm = AsyncMock(
            side_effect=[SearchPlanOutput(queries=["retrieval factuality"]), synthesis]
        )
        mcp_search = AsyncMock(return_value=[self._paper()])

        with (
            patch("citeguard.researcher.activity.request_structured_output", llm),
            patch("citeguard.researcher.activity.search_arxiv_candidates", mcp_search),
        ):
            result = await research_sub_question(self._task())

        self.assertEqual(llm.await_count, 2)
        mcp_search.assert_awaited_once_with(["retrieval factuality"])
        self.assertEqual(
            llm.await_args_list[1].kwargs["max_completion_tokens"],
            SYNTHESIS_MAX_COMPLETION_TOKENS,
        )
        self.assertIs(result.evidence_status, EvidenceStatus.SUPPORTED)

    async def test_no_candidates_still_uses_second_llm_call_for_explanation(self) -> None:
        synthesis = ResearchSynthesisOutput(
            answer="The search returned no candidate papers.",
            evidence_status=EvidenceStatus.NO_RELEVANT_SOURCES,
            evidence_reason="arXiv returned no candidates for the bounded queries.",
            used_source_ids=[],
            assessments=[],
        )
        llm = AsyncMock(
            side_effect=[SearchPlanOutput(queries=["rare research topic"]), synthesis]
        )

        with (
            patch("citeguard.researcher.activity.request_structured_output", llm),
            patch(
                "citeguard.researcher.activity.search_arxiv_candidates",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await research_sub_question(self._task())

        self.assertEqual(llm.await_count, 2)
        self.assertIs(result.evidence_status, EvidenceStatus.NO_RELEVANT_SOURCES)
        self.assertIn("no candidates", result.evidence_reason.lower())

    async def test_reused_subquestion_is_rejected_before_external_calls(self) -> None:
        with self.assertRaises(ApplicationError):
            await research_sub_question(
                self._task(SubQuestionStatus.REUSED_FROM_MEMORY)
            )

    async def test_verifier_feedback_is_an_explicit_capability_gate(self) -> None:
        task = ResearchTaskInput(
            sub_question=self._task().sub_question,
            verifier_feedback="Find evidence for the missing population.",
        )

        with self.assertRaises(ApplicationError):
            await research_sub_question(task)


if __name__ == "__main__":
    unittest.main()
