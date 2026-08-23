"""Convert Planner LLM schemas into stable domain objects."""

from citeguard.domain.research import SubQuestion, SubQuestionStatus
from citeguard.planner.schemas import DecompositionOutput


def assemble_decomposition(output: DecompositionOutput) -> list[SubQuestion]:
    """Convert validated LLM output into stable domain subquestions.

    The LLM chooses question text and ordering. This deterministic boundary owns
    duplicate detection, IDs, and initial status so downstream code never has
    to interpret provider-specific output.

    Args:
        output: Schema-validated decomposition returned by the model boundary.

    Returns:
        New domain subquestions with deterministic per-plan IDs and status.

    Raises:
        ValueError: If two questions are equivalent after case and whitespace
            normalization.
    """

    seen_questions: set[str] = set()
    sub_questions: list[SubQuestion] = []

    for index, item in enumerate(output.items, start=1):
        # Normalize only for comparison. Preserve the original model text in the
        # domain object so validation never silently rewrites user-visible data.
        comparison_key = " ".join(item.question.split()).casefold()

        if comparison_key in seen_questions:
            raise ValueError("Planner returned duplicate subquestions")

        seen_questions.add(comparison_key)
        sub_questions.append(
            SubQuestion(
                # IDs are deterministic within one Planner result. They are not
                # yet persistent or globally unique across sessions.
                id=f"sq-{index:03d}",
                question=item.question,
                # The no-memory path always schedules new research. Reused state
                # will be assembled by the future memory-aware path.
                status=SubQuestionStatus.NEW,
            )
        )

    return sub_questions
