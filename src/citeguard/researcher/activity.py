"""Temporal Activity for the formal single-subquestion Researcher."""

from pydantic import ValidationError
from temporalio import activity
from temporalio.exceptions import ApplicationError

from citeguard.domain.research import ResearchResult, SubQuestionStatus
from citeguard.infrastructure.openrouter import (
    OpenRouterPermanentError,
    request_structured_output,
)
from citeguard.researcher.arxiv import (
    ArxivMcpPermanentError,
    search_arxiv_candidates,
)
from citeguard.researcher.assembly import (
    assemble_insufficient_result,
    assemble_no_relevant_result,
    assemble_supported_result,
    validate_evidence_analysis,
)
from citeguard.researcher.contracts import ResearchTaskInput
from citeguard.researcher.meg import find_minimal_evidence_groups
from citeguard.researcher.prompts import (
    build_evidence_analysis_prompt,
    build_group_support_prompt,
    build_search_plan_prompt,
)
from citeguard.researcher.relevance import RelevanceLevel
from citeguard.researcher.schemas import (
    EvidenceAnalysisOutput,
    EvidenceGroupAssessment,
    EvidenceGroupBatchOutput,
    SearchPlanOutput,
)

ANALYSIS_MAX_COMPLETION_TOKENS = 8_000
GROUP_SUPPORT_MAX_COMPLETION_TOKENS = 8_000


@activity.defn(name="research_sub_question")
async def research_sub_question(input: ResearchTaskInput) -> ResearchResult:
    """Research one fixed target and select a minimal evidence group.

    Query planning and concurrent MCP retrieval precede one evidence-analysis
    decision. Bottom-up MEG search then batches group-support decisions by
    cardinality before deterministic domain assembly.

    Args:
        input: A validated new subquestion without content-retry feedback.

    Returns:
        Structured claims with a minimal group, or an explicit unsupported
        evidence state that never fills gaps with model knowledge.

    Raises:
        ApplicationError: If an unsupported capability is requested or a
            deterministic provider, MCP, schema, or provenance error occurs.

    Retry behavior:
        Transient OpenRouter and MCP failures propagate for Temporal retry.
        Capability and deterministic validation failures are non-retryable.
    """

    if input.sub_question.status is not SubQuestionStatus.NEW:
        raise ApplicationError(
            "Researcher accepts only new subquestions",
            type="InvalidResearchTask",
            non_retryable=True,
        )
    if input.verifier_feedback is not None:
        raise ApplicationError(
            "Researcher content retry is not implemented in this "
            "development slice",
            type="ResearcherContentRetryNotImplemented",
            non_retryable=True,
        )

    try:
        search_plan = await request_structured_output(
            build_search_plan_prompt(input.sub_question),
            SearchPlanOutput,
        )
        candidates = await search_arxiv_candidates(search_plan.queries)
        if not candidates:
            return assemble_no_relevant_result(
                "arXiv returned no candidates for the bounded queries."
            )

        analysis = await request_structured_output(
            build_evidence_analysis_prompt(
                input.sub_question,
                candidates,
            ),
            EvidenceAnalysisOutput,
            max_completion_tokens=ANALYSIS_MAX_COMPLETION_TOKENS,
        )
        claims = validate_evidence_analysis(
            analysis,
            candidates,
            input.sub_question,
        )

        if not claims:
            has_unknown = any(
                assessment.relevance is RelevanceLevel.UNKNOWN
                for assessment in analysis.assessments
            )
            if has_unknown:
                return assemble_insufficient_result(
                    claims=[],
                    unmet_requirement_ids=analysis.unmet_requirement_ids,
                    assessments=analysis.assessments,
                    candidates=candidates,
                    reason=(
                        "Candidate abstracts lacked enough information to "
                        "classify usable evidence."
                    ),
                )
            return assemble_no_relevant_result(
                "No candidate abstract contained answer-bearing evidence."
            )

        if analysis.unmet_requirement_ids:
            return assemble_insufficient_result(
                claims=claims,
                unmet_requirement_ids=analysis.unmet_requirement_ids,
                assessments=analysis.assessments,
                candidates=candidates,
            )

        async def predict_groups(
            groups: list[tuple[str, ...]],
        ) -> list[EvidenceGroupAssessment]:
            output = await request_structured_output(
                build_group_support_prompt(
                    input.sub_question,
                    claims,
                    groups,
                    candidates,
                ),
                EvidenceGroupBatchOutput,
                max_completion_tokens=GROUP_SUPPORT_MAX_COMPLETION_TOKENS,
            )
            return output.items

        groups = await find_minimal_evidence_groups(
            claims=claims,
            requirement_ids=[
                requirement.id
                for requirement in input.sub_question.answer_requirements
            ],
            support_predictor=predict_groups,
        )
        if not groups:
            return assemble_insufficient_result(
                claims=claims,
                unmet_requirement_ids=[],
                assessments=analysis.assessments,
                candidates=candidates,
            )

        return assemble_supported_result(
            claims=claims,
            group=groups[0],
            assessments=analysis.assessments,
            candidates=candidates,
        )
    except (
        ArxivMcpPermanentError,
        OpenRouterPermanentError,
        ValidationError,
        TypeError,
        ValueError,
    ) as exc:
        raise ApplicationError(
            str(exc),
            type="InvalidResearcherResult",
            non_retryable=True,
        ) from exc
