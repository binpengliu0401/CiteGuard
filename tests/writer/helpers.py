"""Shared builders for deterministic Writer behavior tests."""

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


def supported_item(
    sub_question_id: str,
    claim_id: str,
    source_id: str,
    *,
    limitation: str = "One synthetic setting was evaluated.",
) -> SubQuestionResult:
    """Build one supported Writer input item."""

    result = ResearchResult(
        claims=[
            ResearchClaim(
                id=claim_id,
                statement=f"Finding for {sub_question_id}.",
                source_ids=[source_id],
            )
        ],
        evidence_status=EvidenceStatus.SUPPORTED,
        sources=[
            ResearchSource(
                title=f"Study for {sub_question_id}",
                url=f"https://example.test/{source_id}",
                source_id=source_id,
                abstract=f"Finding for {sub_question_id}.",
                supported_aspects="The requested finding.",
                limitations=limitation,
            )
        ],
        evidence_group=EvidenceGroup(source_ids=[source_id]),
    )
    return SubQuestionResult(
        sub_question=_sub_question(sub_question_id),
        result=result,
    )


def insufficient_item(sub_question_id: str) -> SubQuestionResult:
    """Build one partial result with a required evidence reason."""

    source_id = "source-partial"
    result = ResearchResult(
        claims=[
            ResearchClaim(
                id="claim-001",
                statement="One setting contained partial evidence.",
                source_ids=[source_id],
            )
        ],
        evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
        sources=[
            ResearchSource(
                title="Partial evidence study",
                url="https://example.test/partial",
                source_id=source_id,
                abstract="One setting contained partial evidence.",
                supported_aspects="Evidence in one setting.",
                limitations="Other settings were not evaluated.",
            )
        ],
        evidence_reason="The required second setting was not evaluated.",
    )
    return SubQuestionResult(
        sub_question=_sub_question(sub_question_id),
        result=result,
    )


def no_relevant_item(sub_question_id: str) -> SubQuestionResult:
    """Build one source-free result with an explicit reason."""

    return SubQuestionResult(
        sub_question=_sub_question(sub_question_id),
        result=ResearchResult(
            claims=[],
            evidence_status=EvidenceStatus.NO_RELEVANT_SOURCES,
            evidence_reason="No relevant abstract was found.",
        ),
    )


def _sub_question(sub_question_id: str) -> SubQuestion:
    """Build one new subquestion with a fixed answer requirement."""

    return SubQuestion(
        id=sub_question_id,
        question=f"What is the finding for {sub_question_id}?",
        primary_answer_target=f"Finding for {sub_question_id}",
        answer_requirements=[
            AnswerRequirement(
                id=f"req-{sub_question_id}",
                description="State one evidence-backed finding.",
            )
        ],
        status=SubQuestionStatus.NEW,
    )
