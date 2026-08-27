"""Validate Researcher decisions and assemble evidence-domain results."""

from citeguard.domain.research import (
    EvidenceGroup,
    EvidenceStatus,
    ResearchClaim,
    ResearchResult,
    ResearchSource,
    SubQuestion,
)
from citeguard.researcher.arxiv import ArxivPaper
from citeguard.researcher.meg import (
    ClaimCandidate,
    prepare_claim_candidates,
)
from citeguard.researcher.relevance import RelevanceLevel
from citeguard.researcher.schemas import (
    EvidenceAnalysisOutput,
    EvidenceGroupAssessment,
    GroupSupport,
    PaperAssessment,
)


def validate_evidence_analysis(
    output: EvidenceAnalysisOutput,
    candidates: list[ArxivPaper],
    sub_question: SubQuestion,
) -> list[ClaimCandidate]:
    """Validate candidate, requirement, and relevance references.

    Args:
        output: Schema-validated assessments and generated claims.
        candidates: Exact deduplicated papers supplied to the model.
        sub_question: Fixed Planner target and requirements.

    Returns:
        Frozen claim candidates with deterministic project-owned IDs.

    Raises:
        ValueError: If model output omits a candidate, invents an ID, uses
            non-answer-bearing evidence, or does not partition requirements.
    """

    candidate_ids = [candidate.source_id for candidate in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate source IDs must be unique")

    assessment_by_id = {
        assessment.source_id: assessment for assessment in output.assessments
    }
    if set(assessment_by_id) != set(candidate_ids):
        raise ValueError(
            "model assessments must exactly match candidate source IDs"
        )

    requirement_ids = {
        requirement.id for requirement in sub_question.answer_requirements
    }
    unmet_ids = set(output.unmet_requirement_ids)
    if not unmet_ids.issubset(requirement_ids):
        raise ValueError("model used an unknown unmet requirement ID")

    covered_ids: set[str] = set()
    for claim in output.claims:
        claim_requirements = set(claim.requirement_ids)
        if not claim_requirements.issubset(requirement_ids):
            raise ValueError("model used an unknown claim requirement ID")
        covered_ids.update(claim_requirements)
        for source_id in claim.candidate_source_ids:
            assessment = assessment_by_id.get(source_id)
            if assessment is None:
                raise ValueError("model used an unknown claim source ID")
            if assessment.relevance not in {
                RelevanceLevel.DIRECT,
                RelevanceLevel.PARTIAL,
            }:
                raise ValueError(
                    "claims may use only direct or partial sources"
                )

    if covered_ids & unmet_ids:
        raise ValueError("requirements cannot be both covered and unmet")
    if covered_ids | unmet_ids != requirement_ids:
        raise ValueError(
            "claims and unmet IDs must exactly cover answer requirements"
        )
    if covered_ids and not output.claims:
        raise ValueError("covered requirements require generated claims")

    return prepare_claim_candidates(output.claims)


def assemble_supported_result(
    *,
    claims: list[ClaimCandidate],
    group: EvidenceGroupAssessment,
    assessments: list[PaperAssessment],
    candidates: list[ArxivPaper],
) -> ResearchResult:
    """Build a supported result from one validated FULL minimal group."""

    if group.support is not GroupSupport.FULL:
        raise ValueError("supported assembly requires a full evidence group")

    support_by_claim = {
        support.claim_id: support.source_ids
        for support in group.claim_support
    }
    domain_claims = [
        ResearchClaim(
            id=claim.id,
            statement=claim.statement,
            source_ids=support_by_claim[claim.id],
        )
        for claim in claims
    ]
    sources = _assemble_sources(
        source_ids=group.source_ids,
        assessments=assessments,
        candidates=candidates,
    )
    return ResearchResult(
        claims=domain_claims,
        evidence_status=EvidenceStatus.SUPPORTED,
        sources=sources,
        evidence_group=EvidenceGroup(source_ids=group.source_ids),
    )


def assemble_insufficient_result(
    *,
    claims: list[ClaimCandidate],
    unmet_requirement_ids: list[str],
    assessments: list[PaperAssessment],
    candidates: list[ArxivPaper],
    reason: str | None = None,
) -> ResearchResult:
    """Preserve supported partial claims without claiming a complete group."""

    domain_claims = [
        ResearchClaim(
            id=claim.id,
            statement=claim.statement,
            source_ids=claim.candidate_source_ids,
        )
        for claim in claims
    ]
    source_ids = list(
        dict.fromkeys(
            source_id
            for claim in claims
            for source_id in claim.candidate_source_ids
        )
    )
    sources = _assemble_sources(
        source_ids=source_ids,
        assessments=assessments,
        candidates=candidates,
    )
    if reason is None:
        if unmet_requirement_ids:
            missing = ", ".join(unmet_requirement_ids)
            reason = (
                "Candidate abstracts did not support required aspects: "
                f"{missing}."
            )
        else:
            reason = (
                "No candidate source combination fully supported the frozen "
                "claim set."
            )
    return ResearchResult(
        claims=domain_claims,
        evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
        sources=sources,
        evidence_reason=reason,
    )


def assemble_no_relevant_result(reason: str) -> ResearchResult:
    """Build a deterministic source-free result for an empty evidence pool."""

    return ResearchResult(
        claims=[],
        evidence_status=EvidenceStatus.NO_RELEVANT_SOURCES,
        evidence_reason=reason,
    )


def _assemble_sources(
    *,
    source_ids: list[str],
    assessments: list[PaperAssessment],
    candidates: list[ArxivPaper],
) -> list[ResearchSource]:
    """Convert exact candidate IDs into abstract-bounded domain sources."""

    assessment_by_id = {
        assessment.source_id: assessment for assessment in assessments
    }
    candidate_by_id = {
        candidate.source_id: candidate for candidate in candidates
    }
    sources: list[ResearchSource] = []
    for source_id in source_ids:
        assessment = assessment_by_id.get(source_id)
        candidate = candidate_by_id.get(source_id)
        if assessment is None or candidate is None:
            raise ValueError("result source ID was not assessed and retrieved")
        if assessment.supported_aspects is None:
            raise ValueError("result source requires supported aspects")
        sources.append(
            ResearchSource(
                title=candidate.title,
                url=candidate.url,
                source_id=source_id,
                abstract=candidate.summary,
                supported_aspects=assessment.supported_aspects,
                limitations=assessment.limitations,
            )
        )
    return sources
