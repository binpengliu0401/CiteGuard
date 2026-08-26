import unittest

from pydantic import ValidationError

from citeguard.planner.schemas import DecomposedQuestion


class PlannerSchemaTests(unittest.TestCase):
    def test_decomposed_question_accepts_only_question(self) -> None:
        result = DecomposedQuestion(
            question="What is an AI agent?",
        )

        self.assertEqual(
            result.model_dump(),
            {"question": "What is an AI agent?"},
        )

    def test_decomposed_question_rejects_extra_fields(self) -> None:
        with self.assertRaises(ValidationError):
            DecomposedQuestion.model_validate(
                {
                    "question": "What is an AI agent?",
                    "reason": "This field is not part of the schema.",
                }
            )


if __name__ == "__main__":
    unittest.main()
