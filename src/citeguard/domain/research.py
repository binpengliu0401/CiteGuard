"""Domain models shared across the CiteGuard research workflow."""

from dataclasses import dataclass, field
from enum import Enum


class SubQuestionStatus(str, Enum):
    """How a subquestion should be handled by the research workflow."""

    NEW = "new"
    REUSED_FROM_MEMORY = "reused_from_memory"


class EvidenceStatus(str, Enum):
    """Whether retrieved evidence can support the Researcher conclusion."""

    SUPPORTED = "supported"
    NO_RELEVANT_SOURCES = "no_relevant_sources"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class ResearchSource:
    """One source used by a Researcher to support a research conclusion.

    `source_id` and `url` preserve exact provenance. `abstract` is the evidence
    boundary assessed by the current Researcher; it is not a generated summary
    and must not be treated as full-paper evidence.
    """

    title: str
    url: str
    source_id: str
    abstract: str
    supported_aspects: str
    limitations: str

    def __post_init__(self) -> None:
        """Enforce the minimum provenance fields required downstream."""

        _require_non_blank(self.title, "ResearchSource.title")
        _require_non_blank(self.url, "ResearchSource.url")
        _require_non_blank(self.source_id, "ResearchSource.source_id")
        _require_non_blank(self.abstract, "ResearchSource.abstract")
        _require_non_blank(
            self.supported_aspects,
            "ResearchSource.supported_aspects",
        )
        _require_non_blank(self.limitations, "ResearchSource.limitations")


@dataclass(frozen=True)
class AnswerRequirement:
    """One necessary condition for completely answering a subquestion."""

    id: str
    description: str

    def __post_init__(self) -> None:
        """Require stable requirement identity and meaningful content."""

        _require_non_blank(self.id, "AnswerRequirement.id")
        _require_non_blank(
            self.description,
            "AnswerRequirement.description",
        )


@dataclass(frozen=True)
class ResearchClaim:
    """One atomic evidence-bounded finding produced by a Researcher."""

    id: str
    statement: str
    source_ids: list[str]

    def __post_init__(self) -> None:
        """Require an atomic statement with unique source provenance."""

        _require_non_blank(self.id, "ResearchClaim.id")
        _require_non_blank(self.statement, "ResearchClaim.statement")
        _require_unique_non_blank_ids(
            self.source_ids,
            "ResearchClaim.source_ids",
        )


@dataclass(frozen=True)
class EvidenceGroup:
    """The selected minimal source set that jointly supports all claims."""

    source_ids: list[str]

    def __post_init__(self) -> None:
        """Require a nonempty group containing unique source IDs."""

        _require_unique_non_blank_ids(
            self.source_ids,
            "EvidenceGroup.source_ids",
        )


@dataclass(frozen=True)
class ResearchResult:
    """Standard Researcher output and the content reusable by Planner.

    Researcher creates this result for Writer, Verifier, and future Memory.
    Claims, evidence state, explanation, and used sources travel together so
    later modules never have to recover provenance from provider responses.
    """

    claims: list[ResearchClaim]
    evidence_status: EvidenceStatus
    sources: list[ResearchSource] = field(default_factory=list)
    evidence_group: EvidenceGroup | None = None
    evidence_reason: str | None = None

    def __post_init__(self) -> None:
        """Enforce evidence-state invariants before Workflow entry."""

        if not isinstance(self.evidence_status, EvidenceStatus):
            raise TypeError(
                "ResearchResult.evidence_status must be an EvidenceStatus"
            )
        if not isinstance(self.sources, list) or not all(
            isinstance(source, ResearchSource) for source in self.sources
        ):
            raise TypeError(
                "ResearchResult.sources must contain ResearchSource objects"
            )

        if not isinstance(self.claims, list) or not all(
            isinstance(claim, ResearchClaim) for claim in self.claims
        ):
            raise TypeError(
                "ResearchResult.claims must contain ResearchClaim objects"
            )

        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("ResearchResult source IDs must be unique")

        claim_ids = [claim.id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("ResearchResult claim IDs must be unique")

        cited_ids = {
            source_id
            for claim in self.claims
            for source_id in claim.source_ids
        }
        if not cited_ids.issubset(set(source_ids)):
            raise ValueError("claim source IDs must exist in result sources")
        if self.sources and cited_ids != set(source_ids):
            raise ValueError("every result source must support a claim")

        if self.evidence_status is EvidenceStatus.SUPPORTED:
            if not self.claims or not self.sources:
                raise ValueError(
                    "supported research requires claims and sources"
                )
            if not isinstance(self.evidence_group, EvidenceGroup):
                raise ValueError(
                    "supported research requires an evidence group"
                )
            if set(self.evidence_group.source_ids) != set(source_ids):
                raise ValueError(
                    "evidence group must exactly match result sources"
                )
            if self.evidence_reason is not None:
                raise ValueError(
                    "supported research must not have an evidence_reason"
                )
            return

        if self.evidence_reason is None:
            raise ValueError("unsupported research requires an evidence_reason")
        _require_non_blank(
            self.evidence_reason,
            "ResearchResult.evidence_reason",
        )

        if self.evidence_group is not None:
            raise ValueError(
                "unsupported research must not contain an evidence group"
            )

        if (
            self.evidence_status is EvidenceStatus.NO_RELEVANT_SOURCES
            and (self.sources or self.claims)
        ):
            raise ValueError(
                "no_relevant_sources must not contain claims or sources"
            )

        # Insufficient evidence can retain partially useful sources or report
        # that candidate abstracts lacked enough information to classify. In
        # the latter case no source is used in the answer, so the list is empty.
        return


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
    primary_answer_target: str
    answer_requirements: list[AnswerRequirement]
    status: SubQuestionStatus
    reused_result: ResearchResult | None = None
    source_note_id: str | None = None

    def __post_init__(self) -> None:
        """Enforce identity, status, and dependent-field invariants."""

        _require_non_blank(self.id, "SubQuestion.id")
        _require_non_blank(self.question, "SubQuestion.question")
        _require_non_blank(
            self.primary_answer_target,
            "SubQuestion.primary_answer_target",
        )
        if not self.answer_requirements or not all(
            isinstance(requirement, AnswerRequirement)
            for requirement in self.answer_requirements
        ):
            raise ValueError(
                "SubQuestion.answer_requirements must contain requirements"
            )
        requirement_ids = [
            requirement.id for requirement in self.answer_requirements
        ]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("answer requirement IDs must be unique")

        if not isinstance(self.status, SubQuestionStatus):
            raise TypeError("SubQuestion.status must be a SubQuestionStatus")

        # A new task must be sent to a Researcher and therefore cannot carry a
        # historical result or claim provenance from a ResearchNote.
        if self.status is SubQuestionStatus.NEW:
            if (
                self.reused_result is not None
                or self.source_note_id is not None
            ):
                raise ValueError(
                    "reused_result and source_note_id must be empty when "
                    "status is new"
                )
            return

        # Reuse is valid only when the result and source note are known.
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


def _require_unique_non_blank_ids(
    values: list[str],
    field_name: str,
) -> None:
    """Require a nonempty list of unique, nonblank identifier strings."""

    if not isinstance(values, list) or not values:
        raise ValueError(f"{field_name} must not be empty")
    for value in values:
        _require_non_blank(value, field_name)
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must be unique")
