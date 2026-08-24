"""Verify durable Researcher Activity input invariants."""

import unittest

from citeguard.domain.research import SubQuestion, SubQuestionStatus
from citeguard.researcher.contracts import ResearchTaskInput


class ResearchTaskInputTests(unittest.TestCase):
    @staticmethod
    def _sub_question() -> SubQuestion:
        return SubQuestion(
            id="sq-001",
            question="How does retrieval affect factual accuracy?",
            status=SubQuestionStatus.NEW,
        )

    def test_accepts_new_subquestion_without_feedback(self) -> None:
        task = ResearchTaskInput(sub_question=self._sub_question())

        self.assertIsNone(task.verifier_feedback)

    def test_rejects_blank_feedback(self) -> None:
        with self.assertRaisesRegex(ValueError, "verifier_feedback"):
            ResearchTaskInput(
                sub_question=self._sub_question(),
                verifier_feedback="  ",
            )


if __name__ == "__main__":
    unittest.main()
