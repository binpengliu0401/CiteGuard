import json
import re
import unittest

from citeguard.domain.research import (
    EvidenceStatus,
    ResearchNote,
    ResearchResult,
    ResearchSource,
)
from citeguard.planner.prompts import (
    build_decomposition_prompt,
    build_reuse_prompt,
)


class PlannerPromptTests(unittest.TestCase):
    @staticmethod
    def _supported_result() -> ResearchResult:
        return ResearchResult(
            answer="An autonomous system.",
            evidence_status=EvidenceStatus.SUPPORTED,
            sources=[
                ResearchSource(
                    title="Agent systems",
                    url="https://arxiv.org/abs/2401.00001",
                    supported_aspects="The definition of agent systems.",
                    limitations="The paper covers one agent architecture.",
                    source_id="2401.00001",
                )
            ],
        )

    def test_decomposition_prompt_uses_roles_and_json(self) -> None:
        messages = build_decomposition_prompt("What is an AI agent?")

        self.assertEqual([role for role, _ in messages], ["system", "user"])

        payload_text = messages[1][1].split("\n", maxsplit=1)[1]
        payload = json.loads(payload_text)
        self.assertEqual(payload["research_question"], "What is an AI agent?")

    def test_runtime_prompts_are_english_only(self) -> None:
        notes = [
            ResearchNote(
                id="note-1",
                question="What is an AI agent?",
                result=self._supported_result(),
            )
        ]
        messages = build_decomposition_prompt("What is an AI agent?")
        messages += build_reuse_prompt("Define an AI agent.", notes)

        prompt_text = "\n".join(content for _, content in messages)

        self.assertIsNone(re.search(r"[\u4e00-\u9fff]", prompt_text))

    def test_system_prompts_use_structured_policy_sections(self) -> None:
        notes = [
            ResearchNote(
                id="note-1",
                question="What is an AI agent?",
                result=self._supported_result(),
            )
        ]
        prompts = [
            build_decomposition_prompt("What is an AI agent?"),
            build_reuse_prompt("Define an AI agent.", notes),
        ]

        for messages in prompts:
            system_prompt = messages[0][1]
            for section in ("Role", "Task", "Input", "Rules", "Output"):
                self.assertIn(f"{section}\n", system_prompt)

    def test_system_prompts_require_atomic_subquestions(self) -> None:
        notes = [
            ResearchNote(
                id="note-1",
                question="How is a SciFact example represented?",
                result=self._supported_result(),
            )
        ]
        prompts = [
            build_decomposition_prompt(
                "Describe a dataset and report its baseline results."
            ),
            build_reuse_prompt(
                "Describe a dataset and report its baseline results.",
                notes,
            ),
        ]

        for messages in prompts:
            system_prompt = messages[0][1]
            self.assertIn("one primary answer target", system_prompt)
            self.assertIn(
                "Split aspects into separate subquestions",
                system_prompt,
            )
            self.assertIn(
                "comparison itself is the primary answer target",
                system_prompt,
            )


if __name__ == "__main__":
    unittest.main()
