import unittest

from citeguard.domain.research import SubQuestion, SubQuestionStatus
from citeguard.planner.contracts import PlannerActivityInput, PlannerActivityOutput


class PlannerContractTests(unittest.TestCase):
    def test_valid_input(self) -> None:
        planner_input = PlannerActivityInput(
            research_question="What is an AI agent?",
            session_id="session-1",
            existing_notes=[],
        )

        self.assertEqual(planner_input.research_question, "What is an AI agent?")

    def test_blank_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "research_question"):
            PlannerActivityInput(
                research_question="  ",
                session_id="session-1",
                existing_notes=[],
            )

    def test_output_must_not_be_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            PlannerActivityOutput(sub_questions=[])

    def test_valid_output(self) -> None:
        output = PlannerActivityOutput(
            sub_questions=[
                SubQuestion(
                    id="sq-001",
                    question="What is an AI agent?",
                    status=SubQuestionStatus.NEW,
                )
            ]
        )

        self.assertEqual(output.sub_questions[0].id, "sq-001")


if __name__ == "__main__":
    unittest.main()
