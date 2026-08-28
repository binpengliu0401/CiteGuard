"""Serializable contracts used at the Verifier Activity boundary."""

from dataclasses import dataclass

from citeguard.domain.report import WrittenReport
from citeguard.writer.contracts import WriterInput


@dataclass(frozen=True)
class VerifierInput:
    """Writer evidence context and structured report supplied to Verifier.

    The contract retains the exact Writer input rather than reconstructing
    evidence from report citations. Semantic support and unknown identifiers
    remain Verifier decisions rather than constructor validation.
    """

    writer_input: WriterInput
    report: WrittenReport

    def __post_init__(self) -> None:
        """Require typed inputs describing the same original question."""

        if not isinstance(self.writer_input, WriterInput):
            raise TypeError("writer_input must be a WriterInput")
        if not isinstance(self.report, WrittenReport):
            raise TypeError("report must be a WrittenReport")
        if (
            self.writer_input.research_question
            != self.report.research_question
        ):
            raise ValueError(
                "report research question must match Writer input"
            )
