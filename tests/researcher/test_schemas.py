"""Verify structured Researcher evidence-decision schemas."""

import unittest

from pydantic import ValidationError

from citeguard.researcher.relevance import (
    AnswerCoverage,
    ConstraintMatch,
    EvidenceKind,
    MatchLevel,
    RelevanceLevel,
)
from citeguard.researcher.schemas import (
    ClaimSupport,
    EvidenceAnalysisOutput,
    EvidenceGroupAssessment,
    GeneratedClaim,
    GroupSupport,
    PaperAssessment,
    SearchPlanOutput,
)


class ResearcherSchemaTests(unittest.TestCase):
    @staticmethod
    def _assessment(
        source_id: str = "2401.00001",
    ) -> PaperAssessment:
        return PaperAssessment(
            source_id=source_id,
            object_match=MatchLevel.FULL,
            problem_match=MatchLevel.FULL,
            constraint_match=ConstraintMatch.FULL,
            evidence_kind=EvidenceKind.ANSWER_BEARING,
            answer_coverage=AnswerCoverage.PARTIAL,
            supported_aspects="The retrieval method and outcome.",
            limitations="The abstract omits the long-horizon setting.",
        )

    def test_search_plan_requires_distinct_queries(self) -> None:
        with self.assertRaises(ValidationError):
            SearchPlanOutput(queries=["agent memory", " AGENT  MEMORY "])

    def test_assessment_derives_relevance(self) -> None:
        self.assertIs(
            self._assessment().relevance,
            RelevanceLevel.PARTIAL,
        )

    def test_nonusable_assessment_rejects_supported_aspects(self) -> None:
        with self.assertRaises(ValidationError):
            PaperAssessment(
                source_id="2401.00002",
                object_match=MatchLevel.FULL,
                problem_match=MatchLevel.FULL,
                constraint_match=ConstraintMatch.FULL,
                evidence_kind=EvidenceKind.CONTEXT_ONLY,
                answer_coverage=AnswerCoverage.NONE,
                supported_aspects="Background only.",
                limitations="No answer-bearing result.",
            )

    def test_analysis_contains_claims_and_unmet_requirements(self) -> None:
        output = EvidenceAnalysisOutput(
            assessments=[self._assessment()],
            claims=[
                GeneratedClaim(
                    statement="Retrieval improved the reported outcome.",
                    requirement_ids=["req-001"],
                    candidate_source_ids=["2401.00001"],
                )
            ],
            unmet_requirement_ids=["req-002"],
        )

        self.assertEqual(len(output.claims), 1)

    def test_full_group_requires_claim_support_and_no_missing_ids(self) -> None:
        group = EvidenceGroupAssessment(
            source_ids=["2401.00001"],
            support=GroupSupport.FULL,
            claim_support=[
                ClaimSupport(
                    claim_id="claim-001",
                    source_ids=["2401.00001"],
                )
            ],
            missing_claim_ids=[],
            missing_requirement_ids=[],
        )

        self.assertIs(group.support, GroupSupport.FULL)

        with self.assertRaises(ValidationError):
            EvidenceGroupAssessment(
                source_ids=["2401.00001"],
                support=GroupSupport.FULL,
                claim_support=[],
                missing_claim_ids=["claim-001"],
                missing_requirement_ids=[],
            )


if __name__ == "__main__":
    unittest.main()
