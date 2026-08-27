"""Verify Researcher prompt boundaries and fixed-target data."""

import json
import unittest

from citeguard.domain.research import (
    AnswerRequirement,
    SubQuestion,
    SubQuestionStatus,
)
from citeguard.researcher.arxiv import ArxivPaper
from citeguard.researcher.meg import ClaimCandidate
from citeguard.researcher.prompts import (
    build_evidence_analysis_prompt,
    build_group_support_prompt,
    build_search_plan_prompt,
)


class ResearcherPromptTests(unittest.TestCase):
    @staticmethod
    def _subquestion() -> SubQuestion:
        return SubQuestion(
            id="sq-001",
            question="How does retrieval affect factuality?",
            primary_answer_target="Retrieval effects on factuality",
            answer_requirements=[
                AnswerRequirement(
                    id="req-001",
                    description="A retrieval method and factuality outcome",
                )
            ],
            status=SubQuestionStatus.NEW,
        )

    @staticmethod
    def _paper() -> ArxivPaper:
        return ArxivPaper(
            title="Retrieval and factuality",
            source_id="2401.00001",
            summary="We report improved factuality.",
            url="https://arxiv.org/abs/2401.00001",
        )

    def test_search_prompt_contains_fixed_answer_contract(self) -> None:
        messages = build_search_plan_prompt(self._subquestion())
        payload = json.loads(messages[1][1].split("\n", maxsplit=1)[1])

        self.assertEqual(
            payload["primary_answer_target"],
            "Retrieval effects on factuality",
        )
        self.assertEqual(
            payload["answer_requirements"][0]["requirement_id"],
            "req-001",
        )

    def test_analysis_prompt_forbids_free_form_answer(self) -> None:
        messages = build_evidence_analysis_prompt(
            self._subquestion(),
            [self._paper()],
        )
        system_prompt = messages[0][1]

        self.assertIn("frozen candidate ClaimSet", system_prompt)
        self.assertIn("Do not write a\nfree-form answer", system_prompt)

    def test_group_prompt_keeps_claims_and_groups_fixed(self) -> None:
        claims = [
            ClaimCandidate(
                id="claim-001",
                statement="Retrieval improved factuality.",
                requirement_ids=["req-001"],
                candidate_source_ids=["2401.00001"],
            )
        ]
        messages = build_group_support_prompt(
            self._subquestion(),
            claims,
            [("2401.00001",)],
            [self._paper()],
        )
        payload = json.loads(messages[1][1].split("\n", maxsplit=1)[1])

        self.assertEqual(payload["claims"][0]["claim_id"], "claim-001")
        self.assertEqual(payload["source_groups"], [["2401.00001"]])


if __name__ == "__main__":
    unittest.main()
