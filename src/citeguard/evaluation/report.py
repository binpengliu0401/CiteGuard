"""Gold contracts for fixed Writer and Verifier evaluation cases."""

from enum import Enum
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from citeguard.domain.report import (
    VerificationResult,
    WrittenReport,
)
from citeguard.domain.research import EvidenceStatus
from citeguard.verifier.contracts import VerifierInput
from citeguard.writer.contracts import WriterInput


class WriterVerifierCaseKind(str, Enum):
    """The focused behavior exercised by one fixed evaluation case."""

    SUPPORTED_SINGLE_SOURCE = "supported_single_source"
    SUPPORTED_MULTI_SOURCE_MEG = "supported_multi_source_meg"
    INVALID_PROVENANCE = "invalid_provenance"
    CAUSAL_UPGRADE = "causal_upgrade"
    EVIDENCE_STATUS_OVERSTATEMENT = "evidence_status_overstatement"
    TARGETED_LOCALIZATION = "targeted_localization"


class WriterSectionExpectation(BaseModel):
    """Evidence facts that Writer must preserve for one report section."""

    model_config = ConfigDict(extra="forbid")

    sub_question_id: str
    expected_evidence_status: EvidenceStatus
    expected_evidence_reason: str | None = None
    required_claim_ids: list[str]

    @field_validator("sub_question_id")
    @classmethod
    def sub_question_id_must_not_be_blank(cls, value: str) -> str:
        """Require a stable upstream subquestion reference."""

        return _require_non_blank(value, "Writer expectation subquestion ID")

    @field_validator("expected_evidence_reason")
    @classmethod
    def evidence_reason_must_not_be_blank(
        cls,
        value: str | None,
    ) -> str | None:
        """Reject present but empty evidence explanations."""

        if value is not None:
            _require_non_blank(value, "Writer expectation evidence reason")
        return value

    @field_validator("required_claim_ids")
    @classmethod
    def claim_ids_must_be_unique(cls, values: list[str]) -> list[str]:
        """Allow no claims while rejecting ambiguous claim references."""

        return _validate_optional_ids(values, "required claim IDs")


class WriterVerifierGoldCase(BaseModel):
    """One fixed Writer input, candidate report, and Verifier decision."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    kind: WriterVerifierCaseKind
    description: str
    writer_input: WriterInput
    writer_expectations: list[WriterSectionExpectation] = Field(
        min_length=1,
    )
    candidate_report: WrittenReport
    gold_verification: VerificationResult

    @field_validator("case_id", "description")
    @classmethod
    def case_text_must_not_be_blank(cls, value: str) -> str:
        """Require reviewable case identity and intent."""

        return _require_non_blank(value, "Writer/Verifier case text")

    @model_validator(mode="after")
    def validate_fixed_boundary(self) -> Self:
        """Keep every fixture component aligned to one upstream boundary."""

        VerifierInput(
            writer_input=self.writer_input,
            report=self.candidate_report,
        )
        results_by_id = {
            item.sub_question.id: item.result
            for item in self.writer_input.research_results
        }
        expectations_by_id = {
            item.sub_question_id: item
            for item in self.writer_expectations
        }
        if len(expectations_by_id) != len(self.writer_expectations):
            raise ValueError(
                "Writer expectation subquestion IDs must be unique"
            )
        if set(expectations_by_id) != set(results_by_id):
            raise ValueError(
                "Writer expectations must exactly cover research results"
            )
        for sub_question_id, result in results_by_id.items():
            expectation = expectations_by_id[sub_question_id]
            if (
                expectation.expected_evidence_status
                is not result.evidence_status
            ):
                raise ValueError(
                    "Writer expectation evidence status must match research"
                )
            if expectation.expected_evidence_reason != result.evidence_reason:
                raise ValueError(
                    "Writer expectation evidence reason must match research"
                )
            claim_ids = {claim.id for claim in result.claims}
            if set(expectation.required_claim_ids) != claim_ids:
                raise ValueError(
                    "Writer required claims must exactly match research claims"
                )

        section_ids = {
            section.sub_question_id
            for section in self.candidate_report.sections
        }
        if section_ids != set(results_by_id):
            raise ValueError(
                "candidate report sections must exactly cover research results"
            )
        failed_ids = set(
            self.gold_verification.failed_sub_question_ids
        )
        if not failed_ids.issubset(results_by_id):
            raise ValueError(
                "Gold verification failed IDs must reference research results"
            )
        statements_by_id = {
            statement.id: statement
            for section in self.candidate_report.sections
            for statement in section.statements
        }
        for issue in self.gold_verification.issues:
            if issue.statement_id is None:
                continue
            statement = statements_by_id.get(issue.statement_id)
            if statement is None:
                raise ValueError(
                    "Gold issue statement IDs must exist in candidate report"
                )
            if statement.sub_question_id != issue.sub_question_id:
                raise ValueError(
                    "Gold issue statement must match its subquestion scope"
                )
        return self


class WriterVerifierGoldDataset(BaseModel):
    """Versioned synthetic fixture for Writer and Verifier development."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    dataset_id: str
    version: str
    annotation_status: Literal["draft", "reviewed", "frozen"]
    evidence_origin: Literal["synthetic"]
    evaluation_scope: Literal["writer_verifier_fixed_contract"]
    open_adjudications: list[str]
    cases: list[WriterVerifierGoldCase] = Field(min_length=1)

    @field_validator("dataset_id", "version")
    @classmethod
    def identity_must_not_be_blank(cls, value: str) -> str:
        """Require stable dataset identity fields."""

        return _require_non_blank(value, "Writer/Verifier dataset identity")

    @field_validator("open_adjudications")
    @classmethod
    def adjudications_must_be_distinct(
        cls,
        values: list[str],
    ) -> list[str]:
        """Keep unresolved review questions explicit and unambiguous."""

        return _validate_optional_text(values, "open adjudications")

    @model_validator(mode="after")
    def validate_dataset_state(self) -> Self:
        """Require unique cases and honest review-state metadata."""

        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Writer/Verifier case IDs must be unique")
        if self.annotation_status != "draft" and self.open_adjudications:
            raise ValueError(
                "non-draft datasets must not have open adjudications"
            )
        return self


def _require_non_blank(value: str, label: str) -> str:
    """Require meaningful text without silently normalizing it."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be blank")
    return value


def _validate_optional_ids(values: list[str], label: str) -> list[str]:
    """Validate an optional ordered collection of identifier strings."""

    if not isinstance(values, list):
        raise TypeError(f"{label} must be a list")
    for value in values:
        _require_non_blank(value, label)
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")
    return values


def _validate_optional_text(values: list[str], label: str) -> list[str]:
    """Validate optional review notes with normalized uniqueness."""

    _validate_optional_ids(values, label)
    keys = [" ".join(value.split()).casefold() for value in values]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{label} must be distinct")
    return values
