"""Temporal Activity for deterministic Writer synthesis."""

from temporalio import activity

from citeguard.domain.report import WrittenReport
from citeguard.writer.assembly import assemble_report
from citeguard.writer.contracts import WriterInput


@activity.defn(name="write_report")
async def write_report(writer_input: WriterInput) -> WrittenReport:
    """Build one report without tools, model calls, or side effects.

    Args:
        writer_input: Original question and ordered completed research.

    Returns:
        The deterministic provenance-preserving Writer report.

    Retry behavior:
        The current implementation has no external failure boundary. Invalid
        input is rejected by the serializable contract before synthesis.
    """

    return assemble_report(writer_input)
