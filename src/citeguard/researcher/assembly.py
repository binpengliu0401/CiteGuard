"""Convert Researcher model output into stable evidence domain objects."""

from citeguard.domain.research import ResearchResult, ResearchSource
from citeguard.researcher.arxiv import ArxivPaper
from citeguard.researcher.schemas import ResearchSynthesisOutput


def assemble_research_result(
    output: ResearchSynthesisOutput,
    candidates: list[ArxivPaper],
) -> ResearchResult:
    """Build a domain result while enforcing exact candidate provenance.

    Args:
        output: Schema-validated evidence decision from the second model call.
        candidates: Deduplicated papers actually supplied to that model call.

    Returns:
        A domain result containing only sources used in the conclusion.

    Raises:
        ValueError: If candidate IDs are duplicated, assessments are incomplete,
            or the model references a paper it did not receive.
    """

    candidate_by_id: dict[str, ArxivPaper] = {}
    for candidate in candidates:
        if candidate.source_id in candidate_by_id:
            raise ValueError("candidate source IDs must be unique")
        candidate_by_id[candidate.source_id] = candidate

    assessed_ids = {assessment.source_id for assessment in output.assessments}
    if assessed_ids != set(candidate_by_id):
        raise ValueError(
            "model assessments must exactly match candidate source IDs"
        )

    unknown_ids = set(output.used_source_ids) - set(candidate_by_id)
    if unknown_ids:
        raise ValueError("model used a source ID that was not a candidate")

    assessment_by_id = {
        assessment.source_id: assessment for assessment in output.assessments
    }
    sources = []
    for source_id in output.used_source_ids:
        candidate = candidate_by_id[source_id]
        assessment = assessment_by_id[source_id]
        sources.append(
            ResearchSource(
                title=candidate.title,
                url=candidate.url,
                supported_aspects=assessment.supported_aspects,
                limitations=assessment.limitations,
                source_id=source_id,
                summary=candidate.summary,
            )
        )
    return ResearchResult(
        answer=output.answer,
        evidence_status=output.evidence_status,
        sources=sources,
        evidence_reason=output.evidence_reason,
    )
