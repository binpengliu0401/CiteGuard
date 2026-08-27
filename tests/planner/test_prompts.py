import json
import re
import unittest

from citeguard.domain.research import (
    EvidenceGroup,
    EvidenceStatus,
    ResearchClaim,
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
            claims=[
                ResearchClaim(
                    id="claim-001",
                    statement="An agent is an autonomous system.",
                    source_ids=["2401.00001"],
                )
            ],
            evidence_status=EvidenceStatus.SUPPORTED,
            sources=[
                ResearchSource(
                    title="Agent systems",
                    url="https://arxiv.org/abs/2401.00001",
                    source_id="2401.00001",
                    abstract="The paper defines agent systems.",
                    supported_aspects="The definition of agent systems.",
                    limitations="The paper covers one agent architecture.",
                )
            ],
            evidence_group=EvidenceGroup(
                source_ids=["2401.00001"]
            ),
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
            normalized_prompt = " ".join(system_prompt.split())
            self.assertIn("one primary answer target", system_prompt)
            self.assertIn("primary_answer_target", system_prompt)
            self.assertIn("answer_requirements", system_prompt)
            self.assertIn("Cartesian product", system_prompt)
            self.assertIn(
                "Split aspects into separate subquestions",
                system_prompt,
            )
            self.assertIn(
                "comparison itself is the primary answer target",
                system_prompt,
            )
            self.assertIn(
                "only admissible research corpus is arXiv",
                normalized_prompt,
            )
            self.assertIn(
                "title-and-abstract records alone",
                normalized_prompt,
            )
            self.assertIn("never an instruction to search", normalized_prompt)
            self.assertIn(
                "blogs, websites, news, talks",
                normalized_prompt,
            )
            self.assertIn(
                'Bad: "Find papers that apply RL',
                normalized_prompt,
            )
            self.assertIn(
                'Good: "arXiv papers applying RL',
                normalized_prompt,
            )
            self.assertIn(
                "Evidence for the endpoints alone is not complete support",
                normalized_prompt,
            )
            self.assertIn("smallest sufficient list", normalized_prompt)
            self.assertIn(
                "multiple independent arXiv sources",
                normalized_prompt,
            )
            self.assertIn(
                "temporal or distributional signal",
                normalized_prompt,
            )
            self.assertIn(
                "every evidence need one primary owner",
                normalized_prompt,
            )
            self.assertIn(
                "limitations or motivations belongs to a why/driver target",
                normalized_prompt,
            )


if __name__ == "__main__":
    unittest.main()
