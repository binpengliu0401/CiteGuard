"""Verify strict Researcher structured-output and evidence decisions."""

import unittest

from pydantic import ValidationError

from citeguard.domain.research import EvidenceStatus
from citeguard.researcher.schemas import (
    PaperAssessment,
    RelevanceLevel,
    ResearchSynthesisOutput,
    SearchPlanOutput,
)


def assessment(
    source_id: str = "2401.00001",
    relevance: RelevanceLevel = RelevanceLevel.DIRECT,
) -> PaperAssessment:
    return PaperAssessment(
        source_id=source_id,
        relevance=relevance,
        supported_aspects="The evaluated method and reported outcome.",
        limitations="Only the abstract was available for assessment.",
    )


class ResearcherSchemaTests(unittest.TestCase):
    def test_search_plan_accepts_one_to_five_distinct_queries(self) -> None:
        plan = SearchPlanOutput(queries=["retrieval factuality", "RAG verification"])

        self.assertEqual(len(plan.queries), 2)

        with self.assertRaises(ValidationError):
            SearchPlanOutput(queries=[f"query {index}" for index in range(6)])
        with self.assertRaises(ValidationError):
            SearchPlanOutput(queries=["RAG verification", " rag   VERIFICATION "])

    def test_supported_output_requires_a_direct_used_source(self) -> None:
        output = ResearchSynthesisOutput(
            answer="The method improves factual consistency.",
            evidence_status=EvidenceStatus.SUPPORTED,
            evidence_reason=None,
            used_source_ids=["2401.00001"],
            assessments=[assessment()],
        )

        self.assertEqual(output.used_source_ids, ["2401.00001"])

        with self.assertRaises(ValidationError):
            ResearchSynthesisOutput(
                answer="The evidence is direct.",
                evidence_status=EvidenceStatus.SUPPORTED,
                evidence_reason=None,
                used_source_ids=["2401.00001"],
                assessments=[assessment(relevance=RelevanceLevel.PARTIAL)],
            )

    def test_no_relevant_sources_requires_explanation_and_no_relevant_assessment(self) -> None:
        output = ResearchSynthesisOutput(
            answer="No candidate addresses the requested population.",
            evidence_status=EvidenceStatus.NO_RELEVANT_SOURCES,
            evidence_reason="All candidates study a different population.",
            used_source_ids=[],
            assessments=[assessment(relevance=RelevanceLevel.IRRELEVANT)],
        )

        self.assertEqual(output.used_source_ids, [])

        with self.assertRaises(ValidationError):
            ResearchSynthesisOutput(
                answer="No relevant evidence exists.",
                evidence_status=EvidenceStatus.NO_RELEVANT_SOURCES,
                evidence_reason="The evidence does not fully answer the question.",
                used_source_ids=[],
                assessments=[assessment(relevance=RelevanceLevel.PARTIAL)],
            )

    def test_insufficient_evidence_keeps_a_useful_source_and_explanation(self) -> None:
        output = ResearchSynthesisOutput(
            answer="The paper covers the method but not the target setting.",
            evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
            evidence_reason="No paper evaluates the target setting.",
            used_source_ids=["2401.00001"],
            assessments=[assessment(relevance=RelevanceLevel.PARTIAL)],
        )

        self.assertIsNotNone(output.evidence_reason)


if __name__ == "__main__":
    unittest.main()
