import unittest

from pydantic import ValidationError

from citeguard.planner.schemas import DecomposedQuestion


class PlannerSchemaTests(unittest.TestCase):
    def test_decomposed_question_requires_answer_contract(self) -> None:
        result = DecomposedQuestion(
            question="What is an AI agent?",
            primary_answer_target="Definition of an AI agent",
            answer_requirements=["The defining capabilities"],
        )

        self.assertEqual(
            result.model_dump(),
            {
                "question": "What is an AI agent?",
                "primary_answer_target": "Definition of an AI agent",
                "answer_requirements": ["The defining capabilities"],
            },
        )

    def test_decomposed_question_rejects_extra_fields(self) -> None:
        with self.assertRaises(ValidationError):
            DecomposedQuestion.model_validate(
                {
                    "question": "What is an AI agent?",
                    "primary_answer_target": "Definition of an AI agent",
                    "answer_requirements": ["The defining capabilities"],
                    "reason": "This field is not part of the schema.",
                }
            )

    def test_duplicate_requirements_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            DecomposedQuestion(
                question="What is an AI agent?",
                primary_answer_target="Definition of an AI agent",
                answer_requirements=["Capabilities", "  CAPABILITIES  "],
            )

    def test_procedural_requirements_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "research actions"):
            DecomposedQuestion(
                question="Is RL used for memory deletion?",
                primary_answer_target="RL use in memory deletion",
                answer_requirements=[
                    "Find papers that apply RL to memory deletion."
                ],
            )

    def test_schema_describes_arxiv_evidence_boundary(self) -> None:
        properties = DecomposedQuestion.model_json_schema()["properties"]

        self.assertIn("arXiv", properties["question"]["description"])
        requirement_description = properties["answer_requirements"][
            "description"
        ]
        self.assertIn("arXiv", requirement_description)
        self.assertIn("not research actions", requirement_description)
        self.assertIn("smallest sufficient", requirement_description)
        self.assertIn("non-overlapping", requirement_description)


if __name__ == "__main__":
    unittest.main()
