"""Gold contracts and deterministic checks for Writer output."""

from enum import Enum
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from citeguard.domain.report import WrittenReport
from citeguard.domain.research import (
    EvidenceStatus,
    SubQuestionStatus,
)
from citeguard.writer.contracts import WriterInput


class WriterCaseKind(str, Enum):
    """The Writer boundary partition exercised by one Gold case."""

    SUPPORTED_SINGLE_SOURCE = "supported_single_source"
    SUPPORTED_MULTI_CLAIM_MEG = "supported_multi_claim_meg"
    SUPPORTED_JOINT_SOURCE_CLAIM = "supported_joint_source_claim"
    INSUFFICIENT_PARTIAL_EVIDENCE = "insufficient_partial_evidence"
    NO_RELEVANT_SOURCES = "no_relevant_sources"
    MIXED_NEW_AND_REUSED = "mixed_new_and_reused"


class WriterClaimExpectation(BaseModel):
    """Exact upstream provenance that Writer must retain for one Claim."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    source_ids: list[str] = Field(min_length=1)

    @field_validator("claim_id")
    @classmethod
    def claim_id_must_not_be_blank(cls, value: str) -> str:
        """Require a stable Researcher Claim reference."""

        return _require_non_blank(value, "Writer Gold claim ID")

    @field_validator("source_ids")
    @classmethod
    def source_ids_must_be_unique(cls, values: list[str]) -> list[str]:
        """Require exact and unambiguous source provenance."""

        return _validate_ids(values, "Writer Gold source IDs")


class WriterSectionExpectation(BaseModel):
    """Gold facts Writer must preserve for one ordered report section."""

    model_config = ConfigDict(extra="forbid")

    sub_question_id: str
    evidence_status: EvidenceStatus
    evidence_reason: str | None = None
    claims: list[WriterClaimExpectation]

    @field_validator("sub_question_id")
    @classmethod
    def sub_question_id_must_not_be_blank(cls, value: str) -> str:
        """Require a stable section owner."""

        return _require_non_blank(value, "Writer Gold subquestion ID")

    @field_validator("evidence_reason")
    @classmethod
    def evidence_reason_must_not_be_blank(
        cls,
        value: str | None,
    ) -> str | None:
        """Reject present but empty evidence explanations."""

        if value is not None:
            _require_non_blank(value, "Writer Gold evidence reason")
        return value

    @model_validator(mode="after")
    def claim_ids_must_be_unique(self) -> Self:
        """Reject ambiguous Claim expectations within one section."""

        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("Writer Gold section Claim IDs must be unique")
        return self


class WriterGoldCase(BaseModel):
    """One fixed Writer input and structure-first Gold expectation."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    kind: WriterCaseKind
    description: str
    writer_input: WriterInput
    gold_sections: list[WriterSectionExpectation] = Field(min_length=1)

    @field_validator("case_id", "description")
    @classmethod
    def case_text_must_not_be_blank(cls, value: str) -> str:
        """Require reviewable case identity and intent."""

        return _require_non_blank(value, "Writer Gold case text")

    @model_validator(mode="after")
    def gold_must_exactly_match_writer_input(self) -> Self:
        """Derive Gold only from the frozen Researcher result boundary."""

        _collect_input_provenance(self.writer_input)
        expected_ids = [
            item.sub_question.id
            for item in self.writer_input.research_results
        ]
        gold_ids = [section.sub_question_id for section in self.gold_sections]
        if gold_ids != expected_ids:
            raise ValueError(
                "Writer Gold sections must preserve input order and scope"
            )
        results_by_id = {
            item.sub_question.id: item.result
            for item in self.writer_input.research_results
        }
        for section in self.gold_sections:
            result = results_by_id[section.sub_question_id]
            if section.evidence_status is not result.evidence_status:
                raise ValueError(
                    "Writer Gold evidence status must match research"
                )
            if section.evidence_reason != result.evidence_reason:
                raise ValueError(
                    "Writer Gold evidence reason must match research"
                )
            gold_claims = {
                claim.claim_id: set(claim.source_ids)
                for claim in section.claims
            }
            research_claims = {
                claim.id: set(claim.source_ids)
                for claim in result.claims
            }
            if gold_claims != research_claims:
                raise ValueError(
                    "Writer Gold Claim provenance must match research"
                )
        return self


class WriterGoldDataset(BaseModel):
    """Versioned synthetic Gold for the complete Writer v0 boundary."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    dataset_id: str
    version: str
    annotation_status: Literal["draft", "reviewed", "frozen"]
    evidence_origin: Literal["synthetic"]
    evaluation_scope: Literal["writer_fixed_contract"]
    open_adjudications: list[str]
    cases: list[WriterGoldCase] = Field(min_length=1)

    @field_validator("dataset_id", "version")
    @classmethod
    def identity_must_not_be_blank(cls, value: str) -> str:
        """Require stable dataset identity fields."""

        return _require_non_blank(value, "Writer Gold dataset identity")

    @field_validator("open_adjudications")
    @classmethod
    def adjudications_must_be_distinct(
        cls,
        values: list[str],
    ) -> list[str]:
        """Keep unresolved semantic work explicit."""

        return _validate_optional_text(values, "open adjudications")

    @model_validator(mode="after")
    def validate_dataset_coverage(self) -> Self:
        """Require all six contract partitions before accepting Writer v0."""

        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Writer Gold case IDs must be unique")
        kinds = [case.kind for case in self.cases]
        if len(kinds) != len(set(kinds)):
            raise ValueError("Writer Gold case kinds must be unique")
        if set(kinds) != set(WriterCaseKind):
            raise ValueError("Writer Gold must cover every v0 case kind")
        if self.annotation_status != "draft" and self.open_adjudications:
            raise ValueError(
                "non-draft datasets must not have open adjudications"
            )
        _validate_boundary_partitions(self.cases)
        return self


class WriterFailureType(str, Enum):
    """Deterministic failure categories for Writer structure and provenance."""

    RESEARCH_QUESTION_MISMATCH = "research_question_mismatch"
    SECTION_COVERAGE = "section_coverage"
    SECTION_ORDER = "section_order"
    EVIDENCE_STATUS = "evidence_status"
    EVIDENCE_REASON = "evidence_reason"
    MISSING_CLAIM = "missing_claim"
    UNKNOWN_CLAIM = "unknown_claim"
    CLAIM_SCOPE = "claim_scope"
    MISSING_SOURCE = "missing_source"
    UNKNOWN_SOURCE = "unknown_source"
    INVALID_PROVENANCE = "invalid_provenance"
    UNEXPECTED_STATEMENT = "unexpected_statement"


class WriterFailure(BaseModel):
    """One attributable Writer hard-gate failure."""

    model_config = ConfigDict(extra="forbid")

    type: WriterFailureType
    reason: str
    sub_question_id: str | None = None
    statement_id: str | None = None


class WriterMetrics(BaseModel):
    """Deterministic Writer coverage and provenance measurements."""

    model_config = ConfigDict(extra="forbid")

    section_coverage: float
    claim_recall: float
    provenance_precision: float
    provenance_recall: float
    evidence_status_accuracy: float
    evidence_reason_accuracy: float
    unknown_claim_count: int
    unknown_source_count: int


class WriterEvaluationResult(BaseModel):
    """Writer hard-gate result plus structure-first metrics."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    failures: list[WriterFailure]
    metrics: WriterMetrics

    @model_validator(mode="after")
    def passed_must_match_failures(self) -> Self:
        """Prevent contradictory evaluation output."""

        if self.passed == bool(self.failures):
            raise ValueError("Writer pass state must match failures")
        return self


def evaluate_writer_report(
    case: WriterGoldCase,
    report: WrittenReport,
) -> WriterEvaluationResult:
    """Compare one Writer report with deterministic Gold boundary facts."""

    failures: list[WriterFailure] = []
    if report.research_question != case.writer_input.research_question:
        failures.append(
            WriterFailure(
                type=WriterFailureType.RESEARCH_QUESTION_MISMATCH,
                reason="Report research question differs from Writer input.",
            )
        )

    expected_by_id = {
        section.sub_question_id: section
        for section in case.gold_sections
    }
    actual_by_id = {
        section.sub_question_id: section for section in report.sections
    }
    expected_ids = list(expected_by_id)
    actual_ids = list(actual_by_id)
    missing_sections = set(expected_ids) - set(actual_ids)
    unexpected_sections = set(actual_ids) - set(expected_ids)
    for sub_question_id in sorted(missing_sections):
        failures.append(
            WriterFailure(
                type=WriterFailureType.SECTION_COVERAGE,
                sub_question_id=sub_question_id,
                reason="Expected report section is missing.",
            )
        )
    for sub_question_id in sorted(unexpected_sections):
        failures.append(
            WriterFailure(
                type=WriterFailureType.SECTION_COVERAGE,
                sub_question_id=sub_question_id,
                reason="Unexpected report section is present.",
            )
        )
    if not missing_sections and not unexpected_sections:
        if actual_ids != expected_ids:
            failures.append(
                WriterFailure(
                    type=WriterFailureType.SECTION_ORDER,
                    reason="Report section order differs from Writer input.",
                )
            )

    claim_scope, known_sources = _collect_input_provenance(case.writer_input)
    expected_claims = {
        (section.sub_question_id, claim.claim_id)
        for section in case.gold_sections
        for claim in section.claims
    }
    expected_pairs = {
        (section.sub_question_id, claim.claim_id, source_id)
        for section in case.gold_sections
        for claim in section.claims
        for source_id in claim.source_ids
    }
    observed_claims: set[tuple[str, str]] = set()
    observed_pairs: set[tuple[str, str, str]] = set()
    status_matches = 0
    reason_matches = 0
    unknown_claim_count = 0
    unknown_source_count = 0

    for sub_question_id, expectation in expected_by_id.items():
        section = actual_by_id.get(sub_question_id)
        if section is None:
            continue
        if section.evidence_status is expectation.evidence_status:
            status_matches += 1
        else:
            failures.append(
                WriterFailure(
                    type=WriterFailureType.EVIDENCE_STATUS,
                    sub_question_id=sub_question_id,
                    reason="Section evidence status differs from Gold.",
                )
            )
        if section.evidence_reason == expectation.evidence_reason:
            reason_matches += 1
        else:
            failures.append(
                WriterFailure(
                    type=WriterFailureType.EVIDENCE_REASON,
                    sub_question_id=sub_question_id,
                    reason="Section evidence reason differs from Gold.",
                )
            )

        expected_sources_by_claim = {
            claim.claim_id: set(claim.source_ids)
            for claim in expectation.claims
        }
        if not expected_sources_by_claim and section.statements:
            failures.append(
                WriterFailure(
                    type=WriterFailureType.UNEXPECTED_STATEMENT,
                    sub_question_id=sub_question_id,
                    reason="Evidence-free section must not contain statements.",
                )
            )
        for statement in section.statements:
            valid_local_claims: list[str] = []
            for claim_id in statement.claim_ids:
                owners = claim_scope.get(claim_id)
                if owners is None:
                    unknown_claim_count += 1
                    failures.append(
                        WriterFailure(
                            type=WriterFailureType.UNKNOWN_CLAIM,
                            sub_question_id=sub_question_id,
                            statement_id=statement.id,
                            reason=f"Unknown Claim ID: {claim_id}.",
                        )
                    )
                elif sub_question_id not in owners:
                    failures.append(
                        WriterFailure(
                            type=WriterFailureType.CLAIM_SCOPE,
                            sub_question_id=sub_question_id,
                            statement_id=statement.id,
                            reason=(
                                "Claim belongs to other subquestions: "
                                f"{sorted(owners)}; {claim_id}."
                            ),
                        )
                    )
                else:
                    valid_local_claims.append(claim_id)
                    observed_claims.add((sub_question_id, claim_id))

            known_statement_sources: list[str] = []
            for source_id in statement.source_ids:
                if source_id not in known_sources:
                    unknown_source_count += 1
                    failures.append(
                        WriterFailure(
                            type=WriterFailureType.UNKNOWN_SOURCE,
                            sub_question_id=sub_question_id,
                            statement_id=statement.id,
                            reason=f"Unknown source ID: {source_id}.",
                        )
                    )
                else:
                    known_statement_sources.append(source_id)

            expected_statement_sources = {
                source_id
                for claim_id in valid_local_claims
                for source_id in expected_sources_by_claim.get(
                    claim_id,
                    set(),
                )
            }
            attached_sources = set(known_statement_sources)
            missing_sources = expected_statement_sources - attached_sources
            if missing_sources:
                failures.append(
                    WriterFailure(
                        type=WriterFailureType.MISSING_SOURCE,
                        sub_question_id=sub_question_id,
                        statement_id=statement.id,
                        reason=(
                            "Statement omits required sources: "
                            f"{sorted(missing_sources)}."
                        ),
                    )
                )
            statement_pairs = {
                (
                    sub_question_id,
                    claim_id,
                    source_id,
                )
                for claim_id in valid_local_claims
                for source_id in known_statement_sources
            }
            invalid_pairs = statement_pairs - expected_pairs
            if invalid_pairs:
                failures.append(
                    WriterFailure(
                        type=WriterFailureType.INVALID_PROVENANCE,
                        sub_question_id=sub_question_id,
                        statement_id=statement.id,
                        reason=(
                            "Statement creates invalid Claim/source pairs: "
                            f"{sorted(invalid_pairs)}."
                        ),
                    )
                )
            observed_pairs.update(statement_pairs)

        covered_claim_ids = {
            claim_id
            for owner, claim_id in observed_claims
            if owner == sub_question_id
        }
        missing_claims = (
            set(expected_sources_by_claim) - covered_claim_ids
        )
        for claim_id in sorted(missing_claims):
            failures.append(
                WriterFailure(
                    type=WriterFailureType.MISSING_CLAIM,
                    sub_question_id=sub_question_id,
                    reason=f"Expected Claim is missing: {claim_id}.",
                )
            )

    correct_pairs = expected_pairs & observed_pairs
    metrics = WriterMetrics(
        section_coverage=_ratio(
            len(set(expected_ids) & set(actual_ids)),
            len(expected_ids),
        ),
        claim_recall=_ratio(
            len(expected_claims & observed_claims),
            len(expected_claims),
            empty_value=1.0,
        ),
        provenance_precision=_ratio(
            len(correct_pairs),
            len(observed_pairs),
            empty_value=1.0,
        ),
        provenance_recall=_ratio(
            len(correct_pairs),
            len(expected_pairs),
            empty_value=1.0,
        ),
        evidence_status_accuracy=_ratio(
            status_matches,
            len(expected_ids),
        ),
        evidence_reason_accuracy=_ratio(
            reason_matches,
            len(expected_ids),
        ),
        unknown_claim_count=unknown_claim_count,
        unknown_source_count=unknown_source_count,
    )
    return WriterEvaluationResult(
        passed=not failures,
        failures=failures,
        metrics=metrics,
    )


def _collect_input_provenance(
    writer_input: WriterInput,
) -> tuple[dict[str, set[str]], set[str]]:
    """Index global Claim ownership and known source identities."""

    claim_scope: dict[str, set[str]] = {}
    known_sources: set[str] = set()
    for item in writer_input.research_results:
        sub_question_id = item.sub_question.id
        for claim in item.result.claims:
            claim_scope.setdefault(claim.id, set()).add(sub_question_id)
        known_sources.update(source.source_id for source in item.result.sources)
    return claim_scope, known_sources


def _validate_boundary_partitions(cases: list[WriterGoldCase]) -> None:
    """Require the state and cardinality partitions promised by Writer v0."""

    results = [
        item
        for case in cases
        for item in case.writer_input.research_results
    ]
    evidence_statuses = {item.result.evidence_status for item in results}
    if evidence_statuses != set(EvidenceStatus):
        raise ValueError("Writer Gold must cover every evidence status")
    sub_question_statuses = {
        item.sub_question.status for item in results
    }
    if sub_question_statuses != set(SubQuestionStatus):
        raise ValueError("Writer Gold must cover new and reused subquestions")
    claim_counts = {len(item.result.claims) for item in results}
    if not ({0, 1}.issubset(claim_counts) and any(
        count > 1 for count in claim_counts
    )):
        raise ValueError("Writer Gold must cover zero, one, and many Claims")
    meg_sizes = {
        len(item.result.evidence_group.source_ids)
        for item in results
        if item.result.evidence_group is not None
    }
    if 1 not in meg_sizes or not any(size > 1 for size in meg_sizes):
        raise ValueError(
            "Writer Gold must cover singleton and multi-source MEGs"
        )
    if not any(
        len(claim.source_ids) > 1
        for item in results
        for claim in item.result.claims
    ):
        raise ValueError("Writer Gold must cover one jointly supported Claim")
    if not any(len(case.gold_sections) > 1 for case in cases):
        raise ValueError("Writer Gold must cover a multi-section report")


def _require_non_blank(value: str, label: str) -> str:
    """Require meaningful text without rewriting it."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be blank")
    return value


def _validate_ids(values: list[str], label: str) -> list[str]:
    """Require a nonempty list of unique identifier strings."""

    if not values:
        raise ValueError(f"{label} must not be empty")
    for value in values:
        _require_non_blank(value, label)
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")
    return values


def _validate_optional_text(values: list[str], label: str) -> list[str]:
    """Validate optional review notes with normalized uniqueness."""

    if not isinstance(values, list):
        raise TypeError(f"{label} must be a list")
    for value in values:
        _require_non_blank(value, label)
    keys = [" ".join(value.split()).casefold() for value in values]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{label} must be distinct")
    return values


def _ratio(
    numerator: int,
    denominator: int,
    *,
    empty_value: float = 0.0,
) -> float:
    """Return a stable six-decimal metric ratio."""

    if not denominator:
        return empty_value
    return round(numerator / denominator, 6)
