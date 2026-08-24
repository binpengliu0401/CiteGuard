"""Serializable contracts used at the Researcher Activity boundary."""

from dataclasses import dataclass

from citeguard.domain.research import SubQuestion


@dataclass(frozen=True)
class ResearchTaskInput:
    """One subquestion and optional content-retry guidance for a Researcher.

    The subquestion is the stable business scope. Verifier feedback belongs to
    a later content-retry slice and is present in the durable contract now so
    that adding the retry path does not change the Activity boundary.
    """

    sub_question: SubQuestion
    verifier_feedback: str | None = None

    def __post_init__(self) -> None:
        """Reject malformed durable-boundary data before external calls."""

        if not isinstance(self.sub_question, SubQuestion):
            raise TypeError("sub_question must be a SubQuestion")
        if self.verifier_feedback is not None:
            if (
                not isinstance(self.verifier_feedback, str)
                or not self.verifier_feedback.strip()
            ):
                raise ValueError("verifier_feedback must not be blank")
