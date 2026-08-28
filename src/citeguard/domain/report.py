"""Domain models for provenance-preserving reports and verification."""

from dataclasses import dataclass, field
from enum import Enum

from citeguard.domain.research import (
    EvidenceStatus,
    ResearchResult,
    SubQuestion,
    SubQuestionStatus,
)


@dataclass(frozen=True)
class SubQuestionResult:
    """Pair one planned subquestion with its completed research result.

    Workflow aggregation creates this object before Writer execution. The pair
    keeps result provenance attributable when new and memory-reused work are
    combined.
    """

    sub_question: SubQuestion
    result: ResearchResult

    def __post_init__(self) -> None:
        """Require domain objects and preserve exact memory-reuse content."""

        if not isinstance(self.sub_question, SubQuestion):
            raise TypeError("sub_question must be a SubQuestion")
        if not isinstance(self.result, ResearchResult):
            raise TypeError("result must be a ResearchResult")
        if (
            self.sub_question.status is SubQuestionStatus.REUSED_FROM_MEMORY
            and self.result != self.sub_question.reused_result
        ):
            raise ValueError(
                "reused subquestion result must match its reused_result"
            )


@dataclass(frozen=True)
class ReportStatement:
    """One material report statement with exact upstream provenance."""

    id: str
    text: str
    sub_question_id: str
    claim_ids: list[str]
    source_ids: list[str]

    def __post_init__(self) -> None:
        """Require one attributable statement and explicit citations."""

        _require_non_blank(self.id, "ReportStatement.id")
        _require_non_blank(self.text, "ReportStatement.text")
        _require_non_blank(
            self.sub_question_id,
            "ReportStatement.sub_question_id",
        )
        _require_unique_non_blank_ids(
            self.claim_ids,
            "ReportStatement.claim_ids",
        )
        _require_unique_non_blank_ids(
            self.source_ids,
            "ReportStatement.source_ids",
        )


@dataclass(frozen=True)
class ReportSection:
    """Writer output for one subquestion and its inherited evidence state.

    Shape validation deliberately does not decide whether statements are
    supported. Verifier must receive structurally valid but semantically wrong
    reports so it can return attributable content failures.
    """

    sub_question_id: str
    evidence_status: EvidenceStatus
    statements: list[ReportStatement]
    evidence_reason: str | None = None

    def __post_init__(self) -> None:
        """Require typed statements scoped to one section."""

        _require_non_blank(
            self.sub_question_id,
            "ReportSection.sub_question_id",
        )
        if not isinstance(self.evidence_status, EvidenceStatus):
            raise TypeError("evidence_status must be an EvidenceStatus")
        if not isinstance(self.statements, list) or not all(
            isinstance(statement, ReportStatement)
            for statement in self.statements
        ):
            raise TypeError(
                "statements must contain ReportStatement objects"
            )
        statement_ids = [statement.id for statement in self.statements]
        if len(statement_ids) != len(set(statement_ids)):
            raise ValueError("section statement IDs must be unique")
        if any(
            statement.sub_question_id != self.sub_question_id
            for statement in self.statements
        ):
            raise ValueError(
                "section statements must use the section subquestion ID"
            )
        if self.evidence_reason is not None:
            _require_non_blank(
                self.evidence_reason,
                "ReportSection.evidence_reason",
            )


@dataclass(frozen=True)
class WrittenReport:
    """Structured Writer result consumed by Verifier and report rendering."""

    research_question: str
    sections: list[ReportSection]
    limitations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Require unique section and statement identities."""

        _require_non_blank(
            self.research_question,
            "WrittenReport.research_question",
        )
        if not isinstance(self.sections, list):
            raise TypeError("WrittenReport.sections must be a list")
        if not self.sections:
            raise ValueError(
                "WrittenReport.sections must contain report sections"
            )
        if not all(
            isinstance(section, ReportSection) for section in self.sections
        ):
            raise TypeError(
                "WrittenReport.sections must contain ReportSection objects"
            )
        section_ids = [section.sub_question_id for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("report section subquestion IDs must be unique")
        statement_ids = [
            statement.id
            for section in self.sections
            for statement in section.statements
        ]
        if len(statement_ids) != len(set(statement_ids)):
            raise ValueError("report statement IDs must be globally unique")
        _require_optional_unique_text(
            self.limitations,
            "WrittenReport.limitations",
        )


class VerificationIssueType(str, Enum):
    """Stable categories for attributable report-verification failures."""

    MISSING_PROVENANCE = "missing_provenance"
    UNKNOWN_CLAIM = "unknown_claim"
    UNKNOWN_SOURCE = "unknown_source"
    INVALID_PROVENANCE = "invalid_provenance"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    SCOPE_EXPANSION = "scope_expansion"
    CAUSAL_UPGRADE = "causal_upgrade"
    MODALITY_UPGRADE = "modality_upgrade"
    UNSUPPORTED_NUMBER = "unsupported_number"
    EVIDENCE_STATUS_OVERSTATEMENT = "evidence_status_overstatement"


@dataclass(frozen=True)
class VerificationIssue:
    """One typed failure localized to an originating subquestion."""

    type: VerificationIssueType
    sub_question_id: str
    reason: str
    statement_id: str | None = None
    claim_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Require attributable identifiers and a human-readable reason."""

        if not isinstance(self.type, VerificationIssueType):
            raise TypeError("issue type must be a VerificationIssueType")
        _require_non_blank(
            self.sub_question_id,
            "VerificationIssue.sub_question_id",
        )
        _require_non_blank(self.reason, "VerificationIssue.reason")
        if self.statement_id is not None:
            _require_non_blank(
                self.statement_id,
                "VerificationIssue.statement_id",
            )
        _require_optional_unique_ids(
            self.claim_ids,
            "VerificationIssue.claim_ids",
        )
        _require_optional_unique_ids(
            self.source_ids,
            "VerificationIssue.source_ids",
        )


@dataclass(frozen=True)
class VerificationResult:
    """Verifier decision and exact subquestions selected for correction."""

    approved: bool
    issues: list[VerificationIssue]
    failed_sub_question_ids: list[str]

    def __post_init__(self) -> None:
        """Keep approval, issues, and correction scope consistent."""

        if not isinstance(self.approved, bool):
            raise TypeError("approved must be a bool")
        if not isinstance(self.issues, list) or not all(
            isinstance(issue, VerificationIssue) for issue in self.issues
        ):
            raise TypeError("issues must contain VerificationIssue objects")
        _require_optional_unique_ids(
            self.failed_sub_question_ids,
            "VerificationResult.failed_sub_question_ids",
        )
        if self.approved:
            if self.issues or self.failed_sub_question_ids:
                raise ValueError(
                    "approved verification must not contain failures"
                )
            return
        if not self.issues or not self.failed_sub_question_ids:
            raise ValueError(
                "rejected verification requires issues and failed IDs"
            )
        issue_ids = {issue.sub_question_id for issue in self.issues}
        if issue_ids != set(self.failed_sub_question_ids):
            raise ValueError(
                "failed subquestion IDs must exactly match issue scope"
            )


def _require_non_blank(value: str, field_name: str) -> None:
    """Require meaningful domain text without rewriting it."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _require_unique_non_blank_ids(
    values: list[str],
    field_name: str,
) -> None:
    """Require a nonempty collection of unique identifier strings."""

    if not isinstance(values, list) or not values:
        raise ValueError(f"{field_name} must not be empty")
    _require_optional_unique_ids(values, field_name)


def _require_optional_unique_ids(
    values: list[str],
    field_name: str,
) -> None:
    """Validate an optional collection of unique identifier strings."""

    if not isinstance(values, list):
        raise TypeError(f"{field_name} must be a list")
    for value in values:
        _require_non_blank(value, field_name)
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must be unique")


def _require_optional_unique_text(
    values: list[str],
    field_name: str,
) -> None:
    """Validate optional prose entries with normalized uniqueness."""

    _require_optional_unique_ids(values, field_name)
    keys = [" ".join(value.split()).casefold() for value in values]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{field_name} must be distinct")
