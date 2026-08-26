import unittest

from pydantic import ValidationError

from citeguard.domain.research import SubQuestionStatus
from citeguard.planner.assembly import assemble_decomposition
from citeguard.planner.schemas import DecomposedQuestion, DecompositionOutput


class PlannerAssemblyTests(unittest.TestCase):
    def test_assembles_deterministic_new_subquestions(self) -> None:
        output = DecompositionOutput(
            items=[
                DecomposedQuestion(
                    question="Explain the Transformer architecture."
                ),
                DecomposedQuestion(question="Derive self-attention equations."),
            ]
        )

        result = assemble_decomposition(output)

        self.assertEqual([item.id for item in result], ["sq-001", "sq-002"])
        self.assertTrue(
            all(item.status is SubQuestionStatus.NEW for item in result)
        )

    def test_duplicate_subquestions_are_rejected(self) -> None:
        output = DecompositionOutput(
            items=[
                DecomposedQuestion(question="Explain self-attention."),
                DecomposedQuestion(question="  EXPLAIN   SELF-ATTENTION.  "),
            ]
        )

        with self.assertRaisesRegex(ValueError, "duplicate"):
            assemble_decomposition(output)

    def test_atomic_outputs_preserve_separate_research_tasks(self) -> None:
        expected_questions = [
            "What scientific claim-verification task does SciFact define?",
            "How is each example in the SciFact dataset represented?",
            "What do SciFact's baseline experiments establish?",
        ]
        output = DecompositionOutput(
            items=[
                DecomposedQuestion(question=question)
                for question in expected_questions
            ]
        )

        result = assemble_decomposition(output)

        self.assertEqual(
            [item.question for item in result],
            expected_questions,
        )
        self.assertEqual(
            [item.id for item in result],
            ["sq-001", "sq-002", "sq-003"],
        )

    def test_empty_decomposition_is_rejected_by_schema(self) -> None:
        with self.assertRaises(ValidationError):
            DecompositionOutput(items=[])


if __name__ == "__main__":
    unittest.main()
