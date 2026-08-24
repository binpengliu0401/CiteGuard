"""Structured-output schemas for the Researcher's two LLM decisions."""

from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from citeguard.domain.research import EvidenceStatus


class SearchPlanOutput(BaseModel):
    """The first model decision containing bounded arXiv search queries.

    The Researcher Activity consumes this internal schema immediately. Query
    count and normalized uniqueness keep retrieval breadth and cost explicit.
    """

    model_config = ConfigDict(extra="forbid")

    queries: list[str] = Field(
        min_length=1,
        max_length=5,
        description="One to five distinct queries for retrieving candidate papers.",
    )

    @field_validator("queries")
    @classmethod
    def queries_must_be_nonblank_and_distinct(cls, values: list[str]) -> list[str]:
        """Reject empty or duplicate queries without rewriting model text."""

        keys: set[str] = set()
        for value in values:
            if not value.strip():
                raise ValueError("search queries must not be blank")
            key = " ".join(value.split()).casefold()
            if key in keys:
                raise ValueError("search queries must be distinct")
            keys.add(key)
        return values


class RelevanceLevel(str, Enum):
    """How directly one candidate paper can support the exact subquestion."""

    DIRECT = "direct"
    PARTIAL = "partial"
    BACKGROUND = "background"
    IRRELEVANT = "irrelevant"


class PaperAssessment(BaseModel):
    """The second model decision for one supplied candidate paper.

    The source ID must come from candidate data. Support and limitation text
    records why the paper can or cannot contribute to the final answer.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(description="Exact source ID from the candidate data.")
    relevance: RelevanceLevel
    supported_aspects: str = Field(
        description="Exact aspects supported by the title and abstract, or 'none'."
    )
    limitations: str = Field(
        description="Missing support, scope mismatch, or other evidence limitations."
    )

    @field_validator("source_id", "supported_aspects", "limitations")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        """Require explanatory assessment fields for every candidate."""

        if not value.strip():
            raise ValueError("paper assessment text must not be blank")
        return value


class ResearchSynthesisOutput(BaseModel):
    """The second model call's conclusion and per-paper evidence judgments.

    Assembly consumes this internal schema only after its status, explanation,
    used source IDs, and candidate assessments satisfy their joint invariants.
    """

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(description="A concise answer bounded by retrieved evidence.")
    evidence_status: EvidenceStatus
    evidence_reason: str | None = Field(
        description=(
            "Why evidence is absent or insufficient; null only when supported."
        )
    )
    used_source_ids: list[str] = Field(
        description="Candidate source IDs actually used in the answer."
    )
    assessments: list[PaperAssessment] = Field(
        description="One relevance assessment for every candidate paper."
    )

    @field_validator("answer")
    @classmethod
    def answer_must_not_be_blank(cls, value: str) -> str:
        """Reject an empty research conclusion."""

        if not value.strip():
            raise ValueError("answer must not be blank")
        return value

    @field_validator("evidence_reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str | None) -> str | None:
        """Allow either a real explanation or null, never a blank placeholder."""

        if value is not None and not value.strip():
            raise ValueError("evidence_reason must not be blank")
        return value

    @model_validator(mode="after")
    def validate_evidence_decision(self) -> Self:
        """Keep status, used sources, assessments, and explanations consistent."""

        assessment_by_id: dict[str, PaperAssessment] = {}
        for assessment in self.assessments:
            if assessment.source_id in assessment_by_id:
                raise ValueError("assessment source IDs must be unique")
            assessment_by_id[assessment.source_id] = assessment

        if len(self.used_source_ids) != len(set(self.used_source_ids)):
            raise ValueError("used source IDs must be unique")
        if any(source_id not in assessment_by_id for source_id in self.used_source_ids):
            raise ValueError("every used source must have an assessment")

        used_assessments = [
            assessment_by_id[source_id] for source_id in self.used_source_ids
        ]
        if any(
            assessment.relevance
            not in {RelevanceLevel.DIRECT, RelevanceLevel.PARTIAL}
            for assessment in used_assessments
        ):
            raise ValueError("only direct or partial sources may be used")

        if self.evidence_status is EvidenceStatus.SUPPORTED:
            if self.evidence_reason is not None:
                raise ValueError("supported evidence must not have a reason")
            if not self.used_source_ids:
                raise ValueError("supported evidence requires a used source")
            if not any(
                assessment.relevance is RelevanceLevel.DIRECT
                for assessment in used_assessments
            ):
                raise ValueError("supported evidence requires a direct source")
            return self

        if self.evidence_reason is None:
            raise ValueError("unsupported evidence requires a reason")

        if self.evidence_status is EvidenceStatus.NO_RELEVANT_SOURCES:
            if self.used_source_ids:
                raise ValueError("no relevant sources must not use a source")
            if any(
                assessment.relevance
                in {RelevanceLevel.DIRECT, RelevanceLevel.PARTIAL}
                for assessment in self.assessments
            ):
                raise ValueError(
                    "no relevant sources cannot include direct or partial assessments"
                )
            return self

        if not self.used_source_ids:
            raise ValueError("insufficient evidence requires a partially useful source")
        return self
