"""Durable input and result contracts for the CiteGuard Workflow."""

from dataclasses import dataclass

from citeguard.domain.report import VerificationResult, WrittenReport
from citeguard.domain.research import ResearchResult, SubQuestion


@dataclass(frozen=True)
class CiteGuardWorkflowInput:
    """One session-scoped question submitted to the research Workflow."""

    research_question: str
    session_id: str

    def __post_init__(self) -> None:
        """Require stable nonblank question and session identity."""

        _require_non_blank(self.research_question, "research_question")
        _require_non_blank(self.session_id, "session_id")


@dataclass(frozen=True)
class CiteGuardWorkflowResult:
    """Complete minimal-pipeline result, including Verifier rejection.

    A rejected verification is a valid business result. Activity or contract
    failures terminate the Workflow instead of being represented here.
    """

    sub_question: SubQuestion
    research_result: ResearchResult
    report: WrittenReport
    verification: VerificationResult

    def __post_init__(self) -> None:
        """Require typed values from every completed pipeline stage."""

        expected_types = (
            (self.sub_question, SubQuestion, "sub_question"),
            (self.research_result, ResearchResult, "research_result"),
            (self.report, WrittenReport, "report"),
            (self.verification, VerificationResult, "verification"),
        )
        for value, expected_type, field_name in expected_types:
            if not isinstance(value, expected_type):
                raise TypeError(
                    f"{field_name} must be a {expected_type.__name__}"
                )


def _require_non_blank(value: str, field_name: str) -> None:
    """Require meaningful durable-boundary text without rewriting it."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")
