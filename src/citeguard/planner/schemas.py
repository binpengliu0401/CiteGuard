"""Structured-output schemas used by Planner LLM calls."""

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from citeguard.domain.research import SubQuestionStatus

_REQUIREMENT_ACTION_PREFIXES = (
    "describe ",
    "find ",
    "identify ",
    "list ",
    "look for ",
    "look up ",
    "provide ",
    "query ",
    "retrieve ",
    "search ",
)


def _validate_answer_requirements(values: list[str]) -> list[str]:
    """Require distinct evidence conditions rather than research actions."""

    keys: set[str] = set()
    for value in values:
        if not value.strip():
            raise ValueError("answer requirements must not be blank")
        key = " ".join(value.split()).casefold()
        if key.startswith(_REQUIREMENT_ACTION_PREFIXES):
            raise ValueError(
                "answer requirements must state evidence content, not "
                "research actions"
            )
        if key in keys:
            raise ValueError("answer requirements must be distinct")
        keys.add(key)
    return values


class DecomposedQuestion(BaseModel):
    """One subquestion produced by the LLM when no notes are available.

    The legal shape fixes one answer target and its completeness requirements.
    """

    # Accept only fields declared by this schema.
    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        description=(
            "A complete, independently researchable subquestion with one "
            "primary answer target that can be answered using arXiv "
            "title-and-abstract evidence alone."
        ),
    )
    primary_answer_target: str = Field(
        description=(
            "The single relationship, outcome, comparison, or explanation "
            "that the subquestion must answer."
        ),
    )
    answer_requirements: list[str] = Field(
        min_length=1,
        description=(
            "The smallest sufficient set of non-overlapping arXiv evidence "
            "aspects that jointly make the answer complete. State answer "
            "content or coverage conditions, not research actions or "
            "non-arXiv sources."
        ),
    )

    @field_validator("question", "primary_answer_target")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        """Reject empty model output without silently trimming valid text."""

        if not value.strip():
            raise ValueError("planner text must not be blank")
        return value

    @field_validator("answer_requirements")
    @classmethod
    def requirements_must_be_nonblank_and_distinct(
        cls,
        values: list[str],
    ) -> list[str]:
        """Require distinct evidence-content completeness conditions."""

        return _validate_answer_requirements(values)


class DecompositionOutput(BaseModel):
    """Complete no-memory output containing at least one subquestion."""

    # The top-level response is strict for the same reason as each list item:
    # unexpected model prose must fail visibly rather than be ignored.
    model_config = ConfigDict(extra="forbid")

    items: list[DecomposedQuestion] = Field(
        min_length=1,
        description="Subquestions decomposed from the research question.",
    )


class PlannedQuestion(BaseModel):
    """The LLM's planning decision for one subquestion when notes exist.

    This schema is defined for the next memory slice but is not yet used by the
    Planner Activity.
    """

    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        description=(
            "A complete, independently researchable subquestion with one "
            "primary answer target that can be answered using arXiv "
            "title-and-abstract evidence alone."
        ),
    )
    primary_answer_target: str = Field(
        description="The subquestion's single primary answer target.",
    )
    answer_requirements: list[str] = Field(
        min_length=1,
        description=(
            "The smallest sufficient set of non-overlapping arXiv evidence "
            "content for a complete answer, stated as coverage conditions "
            "rather than research actions."
        ),
    )
    status: SubQuestionStatus = Field(
        description=(
            "How to handle the subquestion. new requires new research; "
            "reused_from_memory completely reuses one research note."
        ),
    )
    matched_note_id: str | None = Field(
        description=(
            "The matching ResearchNote ID when status is reused_from_memory; "
            "must be null when status is new."
        ),
    )

    @field_validator("question", "primary_answer_target")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        """Reject a memory-aware plan containing an empty subquestion."""

        if not value.strip():
            raise ValueError("planner text must not be blank")
        return value

    @field_validator("answer_requirements")
    @classmethod
    def requirements_must_be_nonblank_and_distinct(
        cls,
        values: list[str],
    ) -> list[str]:
        """Require distinct evidence-content completeness conditions."""

        return _validate_answer_requirements(values)

    @field_validator("matched_note_id")
    @classmethod
    def matched_note_id_must_not_be_blank(
        cls,
        value: str | None,
    ) -> str | None:
        """Allow either a real note ID or None, never a blank placeholder."""

        if value is not None and not value.strip():
            raise ValueError("matched_note_id must not be a blank string")
        return value

    @model_validator(mode="after")
    def validate_memory_reference(self) -> Self:
        """Keep execution status and note-reference presence consistent."""

        # New research cannot claim a note match. Reuse identifies its note.
        if self.status is SubQuestionStatus.NEW:
            if self.matched_note_id is not None:
                raise ValueError(
                    "matched_note_id must be null when status is new"
                )
            return self

        if self.matched_note_id is None:
            raise ValueError(
                "matched_note_id is required when status is reused_from_memory"
            )

        return self


class PlanningOutput(BaseModel):
    """Complete memory-aware output; defined now but not yet executed."""

    model_config = ConfigDict(extra="forbid")

    items: list[PlannedQuestion] = Field(
        min_length=1,
        description="Decomposed subquestions and their memory-reuse decisions.",
    )
