"""Verify Researcher runtime Prompt structure and trust boundaries."""

import json
import re
import unittest

from citeguard.researcher.arxiv import ArxivPaper
from citeguard.researcher.prompts import (
    build_search_plan_prompt,
    build_synthesis_prompt,
)


class ResearcherPromptTests(unittest.TestCase):
    @staticmethod
    def _paper() -> ArxivPaper:
        return ArxivPaper(
            title="Retrieval and factuality",
            source_id="2401.00001",
            summary="We evaluate retrieval in a controlled setting.",
            url="https://arxiv.org/abs/2401.00001",
        )

    def test_prompts_use_structured_sections_and_json_data(self) -> None:
        prompts = [
            build_search_plan_prompt("Does retrieval improve factuality?"),
            build_synthesis_prompt(
                "Does retrieval improve factuality?",
                [self._paper()],
            ),
        ]

        for messages in prompts:
            self.assertEqual([role for role, _ in messages], ["system", "user"])
            for section in ("Role", "Task", "Input", "Rules", "Output"):
                self.assertIn(f"{section}\n", messages[0][1])
            payload = json.loads(messages[1][1].split("\n", maxsplit=1)[1])
            self.assertEqual(
                payload["sub_question"],
                "Does retrieval improve factuality?",
            )

    def test_synthesis_prompt_contains_the_six_relevance_criteria(self) -> None:
        system_prompt = build_synthesis_prompt("Question", [self._paper()])[0][1]

        for expected in (
            "research object",
            "problem solved",
            "method, setting, time, population",
            "actual method or finding",
            "exact aspects",
            "limitations remain",
        ):
            self.assertIn(expected, system_prompt)

    def test_runtime_prompts_are_english_only(self) -> None:
        messages = build_search_plan_prompt("Does retrieval improve factuality?")
        messages += build_synthesis_prompt(
            "Does retrieval improve factuality?",
            [self._paper()],
        )

        self.assertIsNone(
            re.search(r"[\u4e00-\u9fff]", "\n".join(text for _, text in messages))
        )


if __name__ == "__main__":
    unittest.main()
