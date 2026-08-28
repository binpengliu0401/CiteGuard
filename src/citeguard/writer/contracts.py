"""Serializable contracts used at the Writer Activity boundary."""

from dataclasses import dataclass

from citeguard.domain.report import SubQuestionResult


@dataclass(frozen=True)
class WriterInput:
    """Original question and completed research supplied to Writer.

    Writer receives no search tools or provider objects. Each result remains
    paired with its originating subquestion so every generated statement can
    preserve retry-localizable provenance.
    """

    research_question: str
    research_results: list[SubQuestionResult]

    def __post_init__(self) -> None:
        """Require one unambiguous aggregate of completed research."""

        if (
            not isinstance(self.research_question, str)
            or not self.research_question.strip()
        ):
            raise ValueError("research_question must not be blank")
        if not isinstance(self.research_results, list):
            raise TypeError("research_results must be a list")
        if not self.research_results:
            raise ValueError(
                "research_results must contain completed subquestions"
            )
        if not all(
            isinstance(item, SubQuestionResult)
            for item in self.research_results
        ):
            raise TypeError(
                "research_results must contain SubQuestionResult objects"
            )
        sub_question_ids = [
            item.sub_question.id for item in self.research_results
        ]
        if len(sub_question_ids) != len(set(sub_question_ids)):
            raise ValueError("research result subquestion IDs must be unique")
