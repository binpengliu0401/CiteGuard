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
from citeguard.researcher.assembly import assemble_research_result
from citeguard.researcher.contracts import ResearchTaskInput
from citeguard.researcher.prompts import (
    build_search_plan_prompt,
    build_synthesis_prompt,
)
from citeguard.researcher.schemas import (
    ResearchSynthesisOutput,
    SearchPlanOutput,
)

SYNTHESIS_MAX_COMPLETION_TOKENS = 8_000


@activity.defn(name="research_sub_question")
async def research_sub_question(input: ResearchTaskInput) -> ResearchResult:
    """Research one new subquestion through two bounded model decisions.

    The first model call creates search queries. One MCP session executes those
    queries concurrently, and the second model call evaluates every candidate
    before deterministic domain assembly.

    Args:
        input: A validated new subquestion without content-retry feedback.

    Returns:
        A source-backed or explicitly unsupported domain research result.

    Raises:
        ApplicationError: If an unsupported capability is requested or a
            deterministic provider, MCP, schema, or provenance error occurs.

    Retry behavior:
        Transient OpenRouter and MCP failures propagate for Temporal retry.
        Capability and deterministic validation failures are non-retryable.
    """

    # Reused work already has a result and must not incur a new paid search.
    if input.sub_question.status is not SubQuestionStatus.NEW:
        raise ApplicationError(
            "Researcher accepts only new subquestions",
            type="InvalidResearchTask",
            non_retryable=True,
        )
    # Reject feedback until content retry can actually change research behavior.
    if input.verifier_feedback is not None:
        raise ApplicationError(
            "Researcher content retry is not implemented in this "
            "development slice",
            type="ResearcherContentRetryNotImplemented",
            non_retryable=True,
        )

    try:
        search_plan = await request_structured_output(
            build_search_plan_prompt(input.sub_question.question),
            SearchPlanOutput,
        )
        candidates = await search_arxiv_candidates(search_plan.queries)
        synthesis = await request_structured_output(
            build_synthesis_prompt(input.sub_question.question, candidates),
            ResearchSynthesisOutput,
            # The response contains one explanation per candidate, and provider
            # output ceilings also include hidden reasoning tokens.
            max_completion_tokens=SYNTHESIS_MAX_COMPLETION_TOKENS,
        )
        return assemble_research_result(synthesis, candidates)
    # Transient provider and MCP exceptions intentionally remain unhandled so a
    # future Activity RetryPolicy can retry the same durable research task.
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
