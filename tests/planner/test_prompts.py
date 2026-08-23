import json
import re
import unittest

from citeguard.domain.research import ResearchNote, ResearchResult
from citeguard.planner.prompts import (
    build_decomposition_prompt,
    build_reuse_prompt,
)


class PlannerPromptTests(unittest.TestCase):
    def test_decomposition_prompt_uses_openrouter_roles_and_json_payload(self) -> None:
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
                result=ResearchResult(answer="An autonomous system."),
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
                result=ResearchResult(answer="An autonomous system."),
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


if __name__ == "__main__":
    unittest.main()
