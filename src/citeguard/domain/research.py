"""Domain models shared across the CiteGuard research workflow."""

from dataclasses import dataclass, field
from enum import Enum


class SubQuestionStatus(str, Enum):
    """How a subquestion should be handled by the research workflow."""

    NEW = "new"
    REUSED_FROM_MEMORY = "reused_from_memory"


@dataclass(frozen=True)
class ResearchSource:
    """One source used by a Researcher to support a research conclusion.

    `source_id` is provider-specific metadata, while `url` is the minimum stable
    locator required by later Writer and Verifier modules.
    """

    title: str
    url: str
    source_id: str | None = None
    summary: str | None = None

    def __post_init__(self) -> None:
        """Enforce the minimum provenance fields required downstream."""

        _require_non_blank(self.title, "ResearchSource.title")
        _require_non_blank(self.url, "ResearchSource.url")

        if self.source_id is not None:
            _require_non_blank(self.source_id, "ResearchSource.source_id")


@dataclass(frozen=True)
class ResearchResult:
    """Standard Researcher output and the content reusable by Planner.

    The answer and its supporting sources travel together so later aggregation
    never has to recover provenance from provider-specific responses.
    """

    answer: str
    sources: list[ResearchSource] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Reject an empty research answer before it enters Memory."""

        _require_non_blank(self.answer, "ResearchResult.answer")


@dataclass(frozen=True)
class ResearchNote:
    """A completed research record that a later plan may reuse from Memory.

    The note ID identifies stored evidence; the question records the exact scope
    that must be completely matched before reuse is allowed.
    """

    id: str
    question: str
    result: ResearchResult

    def __post_init__(self) -> None:
        """Require stable note identity and nonempty research scope."""

        _require_non_blank(self.id, "ResearchNote.id")
        _require_non_blank(self.question, "ResearchNote.question")


@dataclass(frozen=True)
class SubQuestion:
    """One executable subquestion returned by Planner to the Workflow.

    State-dependent fields make new research and memory reuse explicit. This
    prevents downstream scheduling from inferring behavior from missing values.
    """

    id: str
    question: str
    status: SubQuestionStatus
    reused_result: ResearchResult | None = None
    source_note_id: str | None = None

    def __post_init__(self) -> None:
        """Enforce identity, status type, and status-dependent field invariants."""

        _require_non_blank(self.id, "SubQuestion.id")
        _require_non_blank(self.question, "SubQuestion.question")

        if not isinstance(self.status, SubQuestionStatus):
            raise TypeError("SubQuestion.status must be a SubQuestionStatus")

        # A new task must be sent to a Researcher and therefore cannot carry a
        # historical result or claim provenance from a ResearchNote.
        if self.status is SubQuestionStatus.NEW:
            if self.reused_result is not None or self.source_note_id is not None:
                raise ValueError(
                    "reused_result and source_note_id must be empty when "
                    "status is new"
                )
            return

        # Reuse is valid only when both the result and its source note are known.
        if self.reused_result is None or self.source_note_id is None:
            raise ValueError(
                "reused_result and source_note_id are required when status is "
                "reused_from_memory"
            )

        _require_non_blank(self.source_note_id, "SubQuestion.source_note_id")


def _require_non_blank(value: str, field_name: str) -> None:
    """Validate required domain text without silently modifying the input."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")
