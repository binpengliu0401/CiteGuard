"""Structured-output schemas for Researcher evidence decisions."""

from enum import Enum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from citeguard.researcher.relevance import (
    AnswerCoverage,
    ConstraintMatch,
    EvidenceKind,
    MatchLevel,
    RelevanceLevel,
    derive_relevance,
)


class SearchPlanOutput(BaseModel):
    """The first model decision containing bounded arXiv queries."""

    model_config = ConfigDict(extra="forbid")

    queries: list[str] = Field(
        min_length=1,
        max_length=5,
        description=(
            "One to five distinct queries for retrieving candidate papers."
        ),
    )

    @field_validator("queries")
    @classmethod
    def queries_must_be_nonblank_and_distinct(
        cls,
        values: list[str],
    ) -> list[str]:
        """Reject empty or duplicate queries without rewriting model text."""

        return _validate_unique_text(values, "search queries")


class PaperAssessment(BaseModel):
    """Factorized evidence judgment for one supplied candidate paper."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(
        description="Exact source ID from the candidate data."
    )
    object_match: MatchLevel = Field(
        description=(
            "Match between the paper and the subquestion's research object."
        )
    )
    problem_match: MatchLevel = Field(
        description="Match between the paper's problem and the subquestion."
    )
    constraint_match: ConstraintMatch = Field(
        description=(
            "Coverage of explicit population, setting, method, time, and "
            "other constraints."
        )
    )
    evidence_kind: EvidenceKind = Field(
        description=(
            "Whether the abstract contains answer-bearing evidence, context "
            "only, no evidence, or insufficient classification information."
        )
    )
    answer_coverage: AnswerCoverage = Field(
        description="How much of the exact answer target the paper covers."
    )
    supported_aspects: str | None = Field(
        description=(
            "Exact aspects supported by the abstract; null when the paper "
            "cannot support an answer."
        )
    )
    limitations: str = Field(
        description="Missing support, scope mismatch, or other limitations."
    )

    @field_validator("source_id", "limitations")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        """Require candidate identity and an explanatory limitation."""

        if not value.strip():
            raise ValueError("paper assessment text must not be blank")
        return value

    @field_validator("supported_aspects")
    @classmethod
    def supported_aspects_must_not_be_blank(
        cls,
        value: str | None,
    ) -> str | None:
        """Allow a real supported aspect or null, never blank text."""

        if value is not None and not value.strip():
            raise ValueError("supported_aspects must not be blank")
        return value

    @model_validator(mode="after")
    def validate_factorized_assessment(self) -> Self:
        """Keep support explanations consistent with derived relevance."""

        if self.relevance in {RelevanceLevel.DIRECT, RelevanceLevel.PARTIAL}:
            if self.supported_aspects is None:
                raise ValueError("usable evidence requires supported_aspects")
            return self

        if self.supported_aspects is not None:
            raise ValueError(
                "background, irrelevant, or unknown evidence must not claim "
                "supported aspects"
            )
        return self

    @property
    def relevance(self) -> RelevanceLevel:
        """Return the deterministic label derived from semantic factors."""

        return derive_relevance(
            object_match=self.object_match,
            problem_match=self.problem_match,
            constraint_match=self.constraint_match,
            evidence_kind=self.evidence_kind,
            answer_coverage=self.answer_coverage,
        )


class GeneratedClaim(BaseModel):
    """One evidence-bounded statement proposed before MEG selection."""

    model_config = ConfigDict(extra="forbid")

    statement: str = Field(
        description="One atomic statement instead of a free-form paragraph."
    )
    requirement_ids: list[str] = Field(
        min_length=1,
        description="Answer requirement IDs satisfied by this claim."
    )
    candidate_source_ids: list[str] = Field(
        min_length=1,
        description="Candidate sources that may support this exact statement."
    )

    @field_validator("statement")
    @classmethod
    def statement_must_not_be_blank(cls, value: str) -> str:
        """Reject an empty proposed claim."""

        if not value.strip():
            raise ValueError("claim statement must not be blank")
        return value

    @field_validator("requirement_ids", "candidate_source_ids")
    @classmethod
    def identifiers_must_be_nonblank_and_distinct(
        cls,
        values: list[str],
    ) -> list[str]:
        """Require unique IDs without accepting blank placeholders."""

        return _validate_unique_text(values, "claim identifiers")


class EvidenceAnalysisOutput(BaseModel):
    """Per-paper assessments and one frozen candidate ClaimSet."""

    model_config = ConfigDict(extra="forbid")

    assessments: list[PaperAssessment] = Field(
        description="One assessment for every supplied candidate paper."
    )
    claims: list[GeneratedClaim] = Field(
        description="Atomic claims grounded in answer-bearing candidates."
    )
    unmet_requirement_ids: list[str] = Field(
        description="Requirements that the entire candidate pool cannot meet."
    )

    @field_validator("unmet_requirement_ids")
    @classmethod
    def unmet_ids_must_be_distinct(cls, values: list[str]) -> list[str]:
        """Reject duplicate or blank missing-requirement identifiers."""

        if not values:
            return values
        return _validate_unique_text(values, "unmet requirement IDs")

    @model_validator(mode="after")
    def assessments_must_have_unique_ids(self) -> Self:
        """Require unique source assessments and claim statements."""

        source_ids = [item.source_id for item in self.assessments]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("assessment source IDs must be unique")
        claim_keys = [
            " ".join(item.statement.split()).casefold()
            for item in self.claims
        ]
        if len(claim_keys) != len(set(claim_keys)):
            raise ValueError("generated claims must be distinct")
        return self


class GroupSupport(str, Enum):
    """Whether one evidence group supports the frozen ClaimSet."""

    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"


class ClaimSupport(BaseModel):
    """Sources in one group that jointly support one fixed claim."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    source_ids: list[str] = Field(min_length=1)

    @field_validator("claim_id")
    @classmethod
    def claim_id_must_not_be_blank(cls, value: str) -> str:
        """Reject a blank claim reference."""

        if not value.strip():
            raise ValueError("claim ID must not be blank")
        return value

    @field_validator("source_ids")
    @classmethod
    def source_ids_must_be_distinct(
        cls,
        values: list[str],
    ) -> list[str]:
        """Require unique source provenance for one claim."""

        return _validate_unique_text(values, "claim support source IDs")


class EvidenceGroupAssessment(BaseModel):
    """One structured support judgment for a supplied source group."""

    model_config = ConfigDict(extra="forbid")

    source_ids: list[str] = Field(min_length=1)
    support: GroupSupport
    claim_support: list[ClaimSupport]
    missing_claim_ids: list[str]
    missing_requirement_ids: list[str]

    @field_validator(
        "source_ids",
        "missing_claim_ids",
        "missing_requirement_ids",
    )
    @classmethod
    def group_identifiers_must_be_distinct(
        cls,
        values: list[str],
    ) -> list[str]:
        """Reject duplicate IDs in group-level identifier lists."""

        if not values:
            return values
        return _validate_unique_text(values, "evidence group identifiers")

    @model_validator(mode="after")
    def support_shape_must_be_consistent(self) -> Self:
        """Keep FULL and NONE labels consistent with explanations."""

        claim_ids = [item.claim_id for item in self.claim_support]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim support IDs must be unique")
        if self.support is GroupSupport.FULL:
            if self.missing_claim_ids or self.missing_requirement_ids:
                raise ValueError("full support must not report missing IDs")
            if not self.claim_support:
                raise ValueError("full support requires claim support")
        if self.support is GroupSupport.NONE and self.claim_support:
            raise ValueError("no support must not report claim support")
        return self


class EvidenceGroupBatchOutput(BaseModel):
    """Support judgments for one bottom-up MEG search level."""

    model_config = ConfigDict(extra="forbid")

    items: list[EvidenceGroupAssessment] = Field(min_length=1)


def _validate_unique_text(values: list[str], label: str) -> list[str]:
    """Require nonblank values unique after normalization."""

    keys: set[str] = set()
    for value in values:
        if not value.strip():
            raise ValueError(f"{label} must not be blank")
        key = " ".join(value.split()).casefold()
        if key in keys:
            raise ValueError(f"{label} must be distinct")
        keys.add(key)
    return values
