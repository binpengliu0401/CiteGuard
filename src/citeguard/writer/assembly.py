"""Deterministic synthesis for the minimal Writer implementation."""

from citeguard.domain.report import (
    ReportSection,
    ReportStatement,
    WrittenReport,
)
from citeguard.writer.contracts import WriterInput


def assemble_report(writer_input: WriterInput) -> WrittenReport:
    """Convert frozen Researcher results into an attributable report.

    The minimal Writer does not paraphrase, merge Claims, call a model, or
    reinterpret evidence. One ResearchClaim becomes one ReportStatement in
    input order. This establishes a safe executable baseline before semantic
    synthesis is added.

    Args:
        writer_input: Original question and ordered completed research.

    Returns:
        A structured report preserving section, Claim, source, and evidence
        state boundaries.
    """

    sections: list[ReportSection] = []
    statement_number = 1
    for item in writer_input.research_results:
        statements: list[ReportStatement] = []
        for claim in item.result.claims:
            statements.append(
                ReportStatement(
                    id=f"statement-{statement_number:03d}",
                    text=claim.statement,
                    sub_question_id=item.sub_question.id,
                    claim_ids=[claim.id],
                    source_ids=list(claim.source_ids),
                )
            )
            statement_number += 1
        sections.append(
            ReportSection(
                sub_question_id=item.sub_question.id,
                evidence_status=item.result.evidence_status,
                statements=statements,
                evidence_reason=item.result.evidence_reason,
            )
        )

    return WrittenReport(
        research_question=writer_input.research_question,
        sections=sections,
        limitations=_collect_limitations(writer_input),
    )


def _collect_limitations(writer_input: WriterInput) -> list[str]:
    """Retain distinct source limitations in stable input order."""

    limitations: list[str] = []
    seen: set[str] = set()
    for item in writer_input.research_results:
        for source in item.result.sources:
            key = " ".join(source.limitations.split()).casefold()
            if key in seen:
                continue
            seen.add(key)
            limitations.append(source.limitations)
    return limitations
