"""Verify Researcher Activity orchestration and capability gates."""

import unittest
from unittest.mock import AsyncMock, patch

from temporalio.exceptions import ApplicationError

from citeguard.domain.research import (
    AnswerRequirement,
    EvidenceStatus,
    ResearchResult,
    SubQuestion,
    SubQuestionStatus,
)
from citeguard.researcher.activity import research_sub_question
from citeguard.researcher.arxiv import ArxivPaper
from citeguard.researcher.contracts import ResearchTaskInput
from citeguard.researcher.relevance import (
    AnswerCoverage,
    ConstraintMatch,
    EvidenceKind,
    MatchLevel,
)
from citeguard.researcher.schemas import (
    ClaimSupport,
    EvidenceAnalysisOutput,
    EvidenceGroupAssessment,
    EvidenceGroupBatchOutput,
    GeneratedClaim,
    GroupSupport,
    PaperAssessment,
    SearchPlanOutput,
)


class ResearcherActivityTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _task(
        status: SubQuestionStatus = SubQuestionStatus.NEW,
    ) -> ResearchTaskInput:
        reused_result = None
        source_note_id = None
        if status is SubQuestionStatus.REUSED_FROM_MEMORY:
            reused_result = ResearchResult(
                claims=[],
                evidence_status=EvidenceStatus.NO_RELEVANT_SOURCES,
                evidence_reason="The previous search found no evidence.",
            )
            source_note_id = "note-001"
        return ResearchTaskInput(
            sub_question=SubQuestion(
                id="sq-001",
                question="Does retrieval improve factuality?",
                primary_answer_target="Retrieval effects on factuality",
                answer_requirements=[
                    AnswerRequirement(
                        id="req-001",
                        description="A method and factuality outcome",
                    )
                ],
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
            summary="We report improved factuality in an evaluation.",
            url="https://arxiv.org/abs/2401.00001",
        )

    @staticmethod
    def _analysis() -> EvidenceAnalysisOutput:
        return EvidenceAnalysisOutput(
            assessments=[
                PaperAssessment(
                    source_id="2401.00001",
                    object_match=MatchLevel.FULL,
                    problem_match=MatchLevel.FULL,
                    constraint_match=ConstraintMatch.FULL,
                    evidence_kind=EvidenceKind.ANSWER_BEARING,
                    answer_coverage=AnswerCoverage.FULL,
                    supported_aspects="The method and factuality outcome.",
                    limitations="The abstract omits full measurements.",
                )
            ],
            claims=[
                GeneratedClaim(
                    statement="Retrieval improved factuality.",
                    requirement_ids=["req-001"],
                    candidate_source_ids=["2401.00001"],
                )
            ],
            unmet_requirement_ids=[],
        )

    async def test_executes_analysis_and_meg_inside_researcher(self) -> None:
        group_output = EvidenceGroupBatchOutput(
            items=[
                EvidenceGroupAssessment(
                    source_ids=["2401.00001"],
                    support=GroupSupport.FULL,
                    claim_support=[
                        ClaimSupport(
                            claim_id="claim-001",
                            source_ids=["2401.00001"],
                        )
                    ],
                    missing_claim_ids=[],
                    missing_requirement_ids=[],
                )
            ]
        )
        llm = AsyncMock(
            side_effect=[
                SearchPlanOutput(queries=["retrieval factuality"]),
                self._analysis(),
                group_output,
            ]
        )
        mcp_search = AsyncMock(return_value=[self._paper()])

        with (
            patch(
                "citeguard.researcher.activity.request_structured_output",
                llm,
            ),
            patch(
                "citeguard.researcher.activity.search_arxiv_candidates",
                mcp_search,
            ),
        ):
            result = await research_sub_question(self._task())

        self.assertEqual(llm.await_count, 3)
        self.assertIs(result.evidence_status, EvidenceStatus.SUPPORTED)
        self.assertEqual(result.evidence_group.source_ids, ["2401.00001"])

    async def test_no_candidates_skips_evidence_model_calls(self) -> None:
        llm = AsyncMock(
            return_value=SearchPlanOutput(queries=["rare research topic"])
        )

        with (
            patch(
                "citeguard.researcher.activity.request_structured_output",
                llm,
            ),
            patch(
                "citeguard.researcher.activity.search_arxiv_candidates",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await research_sub_question(self._task())

        self.assertEqual(llm.await_count, 1)
        self.assertIs(
            result.evidence_status,
            EvidenceStatus.NO_RELEVANT_SOURCES,
        )

    async def test_reused_subquestion_is_rejected_early(self) -> None:
        with self.assertRaises(ApplicationError):
            await research_sub_question(
                self._task(SubQuestionStatus.REUSED_FROM_MEMORY)
            )

    async def test_verifier_feedback_is_a_capability_gate(self) -> None:
        task = ResearchTaskInput(
            sub_question=self._task().sub_question,
            verifier_feedback="Find evidence for the missing population.",
        )

        with self.assertRaises(ApplicationError):
            await research_sub_question(task)


if __name__ == "__main__":
    unittest.main()
