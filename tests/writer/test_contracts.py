"""Verify durable Writer input invariants."""

import unittest

from citeguard.domain.report import SubQuestionResult
from citeguard.domain.research import (
    AnswerRequirement,
    EvidenceGroup,
    EvidenceStatus,
    ResearchClaim,
    ResearchResult,
    ResearchSource,
    SubQuestion,
    SubQuestionStatus,
)
from citeguard.writer.contracts import WriterInput


def completed_research() -> SubQuestionResult:
    """Build one supported result paired with its planned scope."""

    return SubQuestionResult(
        sub_question=SubQuestion(
            id="sq-001",
            question="Does retrieval improve factual accuracy?",
            primary_answer_target="Retrieval effects on factual accuracy",
            answer_requirements=[
                AnswerRequirement(
                    id="req-001",
                    description="A measured factual-accuracy outcome",
                )
            ],
            status=SubQuestionStatus.NEW,
        ),
        result=ResearchResult(
            claims=[
                ResearchClaim(
                    id="claim-001",
                    statement="Retrieval improved factual accuracy.",
                    source_ids=["2401.00001"],
                )
            ],
            evidence_status=EvidenceStatus.SUPPORTED,
            sources=[
                ResearchSource(
                    title="Retrieval and factual accuracy",
                    url="https://arxiv.org/abs/2401.00001",
                    source_id="2401.00001",
                    abstract="Retrieval improved factual accuracy.",
                    supported_aspects="The measured accuracy outcome.",
                    limitations="One evaluation setting was reported.",
                )
            ],
            evidence_group=EvidenceGroup(
                source_ids=["2401.00001"]
            ),
        ),
    )


class WriterInputTests(unittest.TestCase):
    def test_accepts_attributable_research_aggregate(self) -> None:
        writer_input = WriterInput(
            research_question="Does retrieval improve factual accuracy?",
            research_results=[completed_research()],
        )

        self.assertEqual(
            writer_input.research_results[0].sub_question.id,
            "sq-001",
        )

    def test_rejects_duplicate_subquestion_results(self) -> None:
        item = completed_research()

        with self.assertRaisesRegex(TypeError, "must be a list"):
            WriterInput(
                research_question="Does retrieval improve factual accuracy?",
                research_results=(item,),  # type: ignore[arg-type]
            )

        with self.assertRaisesRegex(ValueError, "must be unique"):
            WriterInput(
                research_question="Does retrieval improve factual accuracy?",
                research_results=[item, item],
            )

    def test_reused_result_must_match_planner_content(self) -> None:
        item = completed_research()
        reused_sub_question = SubQuestion(
            id="sq-reused-001",
            question=item.sub_question.question,
            primary_answer_target=item.sub_question.primary_answer_target,
            answer_requirements=item.sub_question.answer_requirements,
            status=SubQuestionStatus.REUSED_FROM_MEMORY,
            reused_result=item.result,
            source_note_id="note-001",
        )
        different_result = ResearchResult(
            claims=[],
            evidence_status=EvidenceStatus.NO_RELEVANT_SOURCES,
            evidence_reason="The stored candidates were not relevant.",
        )

        with self.assertRaisesRegex(ValueError, "must match"):
            SubQuestionResult(
                sub_question=reused_sub_question,
                result=different_result,
            )


if __name__ == "__main__":
    unittest.main()
