"""Temporal Activity for the Planner's first no-memory execution path."""

from pydantic import ValidationError
from temporalio import activity
from temporalio.exceptions import ApplicationError

from citeguard.infrastructure.openrouter import (
    OpenRouterPermanentError,
    request_structured_output,
)
from citeguard.planner.assembly import assemble_decomposition
from citeguard.planner.contracts import (
    PlannerActivityInput,
    PlannerActivityOutput,
)
from citeguard.planner.prompts import build_decomposition_prompt
from citeguard.planner.schemas import DecompositionOutput


@activity.defn(name="plan_research")
async def plan_research(
    input: PlannerActivityInput,
) -> PlannerActivityOutput:
    """Create new subquestions through the implemented no-memory path.

    This Activity is the Planner's orchestration boundary. Prompt construction,
    provider I/O, schema validation, and domain assembly stay in their owning
    modules so Temporal-specific failure policy remains visible here.

    Args:
        input: Validated session-scoped question and available research notes.

    Returns:
        A Planner result containing validated, executable subquestions.

    Raises:
        ApplicationError: If memory reuse is requested or the provider returns
            a deterministic invalid result that retrying cannot repair.

    Retry behavior:
        Transient OpenRouter failures propagate so Temporal may retry them.
        Unsupported capabilities and deterministic validation failures are
        converted to non-retryable ApplicationErrors.
    """

    # Nonempty notes request memory-aware planning. Failing explicitly prevents
    # the current slice from silently ignoring reusable research and returning
    # a plan that looks successful but has incorrect business semantics.
    if input.existing_notes:
        raise ApplicationError(
            "Planner memory reuse is not implemented in this development slice",
            type="PlannerMemoryNotImplemented",
            non_retryable=True,
        )

    try:
        llm_output = await request_structured_output(
            build_decomposition_prompt(input.research_question),
            DecompositionOutput,
        )
        sub_questions = assemble_decomposition(llm_output)
        return PlannerActivityOutput(sub_questions=sub_questions)
    # Permanent provider failures and deterministic validation failures should
    # not consume Temporal retries. OpenRouterTransientError is intentionally
    # absent: it propagates so a future Activity RetryPolicy can retry it.
    except (OpenRouterPermanentError, ValidationError, ValueError) as exc:
        raise ApplicationError(
            str(exc),
            type="InvalidPlannerResult",
            non_retryable=True,
        ) from exc
