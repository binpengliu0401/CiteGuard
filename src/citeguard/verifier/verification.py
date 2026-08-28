"""Deterministic provenance and evidence-state verification."""

from citeguard.domain.report import (
    ReportStatement,
    VerificationIssue,
    VerificationIssueType,
    VerificationResult,
)
from citeguard.domain.research import EvidenceStatus, ResearchClaim
from citeguard.verifier.contracts import VerifierInput


def verify_report(verifier_input: VerifierInput) -> VerificationResult:
    """Apply deterministic hard gates to one structured report.

    The baseline approves only exact frozen Claim text with exact scoped source
    provenance. It does not infer entailment or assign fine-grained semantic
    overclaim types from free text.

    Args:
        verifier_input: Exact Writer evidence context and candidate report.

    Returns:
        Approval or typed issues localized to input subquestions.

    Raises:
        ValueError: If the report invents a section outside Writer input. Such
            a section cannot be mapped to a valid Researcher retry target.
    """

    writer_input = verifier_input.writer_input
    report = verifier_input.report
    results_by_id = {
        item.sub_question.id: item.result
        for item in writer_input.research_results
    }
    sections_by_id = {
        section.sub_question_id: section for section in report.sections
    }
    unexpected_sections = set(sections_by_id) - set(results_by_id)
    if unexpected_sections:
        raise ValueError(
            "report contains sections outside Writer input: "
            f"{sorted(unexpected_sections)}"
        )

    claim_scopes, known_sources = _index_input(verifier_input)
    issues: list[VerificationIssue] = []
    for item in writer_input.research_results:
        sub_question_id = item.sub_question.id
        section = sections_by_id.get(sub_question_id)
        if section is None:
            issues.append(
                VerificationIssue(
                    type=VerificationIssueType.MISSING_PROVENANCE,
                    sub_question_id=sub_question_id,
                    reason="The report omitted the research-result section.",
                    claim_ids=[claim.id for claim in item.result.claims],
                    source_ids=_claim_source_ids(item.result.claims),
                )
            )
            continue

        status_valid = _verify_evidence_state(
            sub_question_id=sub_question_id,
            expected_status=item.result.evidence_status,
            expected_reason=item.result.evidence_reason,
            actual_status=section.evidence_status,
            actual_reason=section.evidence_reason,
            issues=issues,
        )
        _verify_section_statements(
            sub_question_id=sub_question_id,
            expected_claims={
                claim.id: claim for claim in item.result.claims
            },
            statements=section.statements,
            claim_scopes=claim_scopes,
            known_sources=known_sources,
            check_exact_text=status_valid,
            issues=issues,
        )

    failed_scope = {issue.sub_question_id for issue in issues}
    failed_ids = [
        item.sub_question.id
        for item in writer_input.research_results
        if item.sub_question.id in failed_scope
    ]
    return VerificationResult(
        approved=not issues,
        issues=issues,
        failed_sub_question_ids=failed_ids,
    )


def _verify_evidence_state(
    *,
    sub_question_id: str,
    expected_status: EvidenceStatus,
    expected_reason: str | None,
    actual_status: EvidenceStatus,
    actual_reason: str | None,
    issues: list[VerificationIssue],
) -> bool:
    """Require exact status and reason inheritance from Researcher output."""

    if actual_status is expected_status and actual_reason == expected_reason:
        return True
    overstates = (
        expected_status is not EvidenceStatus.SUPPORTED
        and (
            actual_status is EvidenceStatus.SUPPORTED
            or actual_reason is None
        )
    )
    issue_type = (
        VerificationIssueType.EVIDENCE_STATUS_OVERSTATEMENT
        if overstates
        else VerificationIssueType.UNSUPPORTED
    )
    issues.append(
        VerificationIssue(
            type=issue_type,
            sub_question_id=sub_question_id,
            reason=(
                "Report evidence status or reason differs from the "
                "Researcher result."
            ),
        )
    )
    return False


def _verify_section_statements(
    *,
    sub_question_id: str,
    expected_claims: dict[str, ResearchClaim],
    statements: list[ReportStatement],
    claim_scopes: dict[str, set[str]],
    known_sources: set[str],
    check_exact_text: bool,
    issues: list[VerificationIssue],
) -> None:
    """Check Claim coverage, scoped identity, source edges, and exact text."""

    covered_claims: set[str] = set()
    for statement in statements:
        local_claims: list[ResearchClaim] = []
        identity_error = False
        for claim_id in statement.claim_ids:
            claim = expected_claims.get(claim_id)
            if claim is not None:
                local_claims.append(claim)
                continue
            owners = claim_scopes.get(claim_id)
            issue_type = (
                VerificationIssueType.UNKNOWN_CLAIM
                if owners is None
                else VerificationIssueType.INVALID_PROVENANCE
            )
            reason = (
                f"Unknown Claim ID: {claim_id}."
                if owners is None
                else (
                    "Claim belongs to other subquestions: "
                    f"{sorted(owners)}; {claim_id}."
                )
            )
            issues.append(
                VerificationIssue(
                    type=issue_type,
                    sub_question_id=sub_question_id,
                    statement_id=statement.id,
                    reason=reason,
                    claim_ids=[claim_id],
                )
            )
            identity_error = True

        unknown_sources = [
            source_id
            for source_id in statement.source_ids
            if source_id not in known_sources
        ]
        if unknown_sources:
            issues.append(
                VerificationIssue(
                    type=VerificationIssueType.UNKNOWN_SOURCE,
                    sub_question_id=sub_question_id,
                    statement_id=statement.id,
                    reason=f"Unknown source IDs: {unknown_sources}.",
                    source_ids=unknown_sources,
                )
            )
            identity_error = True

        repeated_claims = [
            claim.id for claim in local_claims if claim.id in covered_claims
        ]
        if repeated_claims:
            issues.append(
                VerificationIssue(
                    type=VerificationIssueType.INVALID_PROVENANCE,
                    sub_question_id=sub_question_id,
                    statement_id=statement.id,
                    reason=f"Claims appear more than once: {repeated_claims}.",
                    claim_ids=repeated_claims,
                )
            )
            identity_error = True
        covered_claims.update(claim.id for claim in local_claims)

        provenance_error = _verify_statement_provenance(
            sub_question_id=sub_question_id,
            statement_id=statement.id,
            claims=local_claims,
            source_ids=[
                source_id
                for source_id in statement.source_ids
                if source_id in known_sources
            ],
            issues=issues,
        )
        if (
            check_exact_text
            and not identity_error
            and not provenance_error
            and (
                len(local_claims) != 1
                or statement.text != local_claims[0].statement
            )
        ):
            issues.append(
                VerificationIssue(
                    type=VerificationIssueType.UNSUPPORTED,
                    sub_question_id=sub_question_id,
                    statement_id=statement.id,
                    reason=(
                        "Deterministic verification licenses only one exact "
                        "frozen Claim per statement."
                    ),
                    claim_ids=[claim.id for claim in local_claims],
                    source_ids=list(statement.source_ids),
                )
            )

    missing_claims = set(expected_claims) - covered_claims
    if missing_claims:
        issues.append(
            VerificationIssue(
                type=VerificationIssueType.MISSING_PROVENANCE,
                sub_question_id=sub_question_id,
                reason=f"Report omitted Claims: {sorted(missing_claims)}.",
                claim_ids=sorted(missing_claims),
                source_ids=_claim_source_ids(
                    [expected_claims[item] for item in missing_claims]
                ),
            )
        )


def _verify_statement_provenance(
    *,
    sub_question_id: str,
    statement_id: str,
    claims: list[ResearchClaim],
    source_ids: list[str],
    issues: list[VerificationIssue],
) -> bool:
    """Require exact Claim/source edges, including atomic Claim separation."""

    if not claims:
        return False
    expected_pairs = {
        (claim.id, source_id)
        for claim in claims
        for source_id in claim.source_ids
    }
    actual_pairs = {
        (claim.id, source_id)
        for claim in claims
        for source_id in source_ids
    }
    if actual_pairs == expected_pairs:
        return False
    missing_pairs = sorted(expected_pairs - actual_pairs)
    invalid_pairs = sorted(actual_pairs - expected_pairs)
    issues.append(
        VerificationIssue(
            type=VerificationIssueType.INVALID_PROVENANCE,
            sub_question_id=sub_question_id,
            statement_id=statement_id,
            reason=(
                "Claim/source provenance differs from Researcher output; "
                f"missing={missing_pairs}, invalid={invalid_pairs}."
            ),
            claim_ids=[claim.id for claim in claims],
            source_ids=list(source_ids),
        )
    )
    return True


def _index_input(
    verifier_input: VerifierInput,
) -> tuple[dict[str, set[str]], set[str]]:
    """Index subquestion-scoped Claim IDs and known source IDs."""

    claim_scopes: dict[str, set[str]] = {}
    known_sources: set[str] = set()
    for item in verifier_input.writer_input.research_results:
        sub_question_id = item.sub_question.id
        for claim in item.result.claims:
            claim_scopes.setdefault(claim.id, set()).add(sub_question_id)
        known_sources.update(source.source_id for source in item.result.sources)
    return claim_scopes, known_sources


def _claim_source_ids(claims: list[ResearchClaim]) -> list[str]:
    """Collect unique Claim sources in stable Claim order."""

    return list(
        dict.fromkeys(
            source_id
            for claim in claims
            for source_id in claim.source_ids
        )
    )
