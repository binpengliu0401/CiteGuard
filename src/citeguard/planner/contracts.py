"""Serializable contracts used at the Planner Activity boundary."""

from dataclasses import dataclass

from citeguard.domain.research import ResearchNote, SubQuestion


@dataclass(frozen=True)
class PlannerActivityInput:
    """Stable input passed from a Workflow to the Planner Activity.

    `session_id` scopes future memory lookup, while `existing_notes` carries the
    already-resolved note candidates. The current Activity accepts only an
    empty note list, but the boundary is defined now so the later memory slice
    does not need to change the durable contract.
    """

    research_question: str
    session_id: str
    existing_notes: list[ResearchNote]

    def __post_init__(self) -> None:
        """Reject malformed durable-boundary data before any side effect."""

        # Dataclass type annotations are not runtime validators. Explicit checks
        # make failures immediate for Temporal and local input.
        _require_non_blank(self.research_question, "research_question")
        _require_non_blank(self.session_id, "session_id")

        if not isinstance(self.existing_notes, list):
            raise TypeError("existing_notes must be a list")

        if not all(
            isinstance(note, ResearchNote)
            for note in self.existing_notes
        ):
            raise TypeError(
                "existing_notes must contain only ResearchNote objects"
            )


@dataclass(frozen=True)
class PlannerActivityOutput:
    """Stable Planner result recorded in Temporal Workflow history.

    LLM-facing Pydantic schemas never cross this boundary; the Workflow receives
    only project-owned domain objects with their invariants already enforced.
    """

    sub_questions: list[SubQuestion]

    def __post_init__(self) -> None:
        """Require a nonempty list containing only domain subquestions."""

        if not self.sub_questions:
            raise ValueError("sub_questions must not be empty")

        if not all(
            isinstance(sub_question, SubQuestion)
            for sub_question in self.sub_questions
        ):
            raise TypeError(
                "sub_questions must contain only SubQuestion objects"
            )


def _require_non_blank(value: str, field_name: str) -> None:
    """Validate required text without trimming or otherwise rewriting it."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")
