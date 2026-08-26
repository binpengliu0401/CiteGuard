"""Verify strict Researcher structured-output and evidence decisions."""

import unittest

from pydantic import ValidationError

from citeguard.domain.research import EvidenceStatus
from citeguard.researcher.relevance import (
    AnswerCoverage,
    ConstraintMatch,
    EvidenceKind,
    MatchLevel,
    RelevanceLevel,
)
from citeguard.researcher.schemas import (
    PaperAssessment,
    ResearchSynthesisOutput,
    SearchPlanOutput,
)


def assessment(
    source_id: str = "2401.00001",
    relevance: RelevanceLevel = RelevanceLevel.DIRECT,
) -> PaperAssessment:
    factor_sets = {
        RelevanceLevel.DIRECT: {
            "object_match": MatchLevel.FULL,
            "problem_match": MatchLevel.FULL,
            "constraint_match": ConstraintMatch.FULL,
            "evidence_kind": EvidenceKind.ANSWER_BEARING,
            "answer_coverage": AnswerCoverage.FULL,
        },
        RelevanceLevel.PARTIAL: {
            "object_match": MatchLevel.FULL,
            "problem_match": MatchLevel.FULL,
            "constraint_match": ConstraintMatch.PARTIAL,
            "evidence_kind": EvidenceKind.ANSWER_BEARING,
            "answer_coverage": AnswerCoverage.PARTIAL,
        },
        RelevanceLevel.BACKGROUND: {
            "object_match": MatchLevel.FULL,
            "problem_match": MatchLevel.PARTIAL,
            "constraint_match": ConstraintMatch.PARTIAL,
            "evidence_kind": EvidenceKind.CONTEXT_ONLY,
            "answer_coverage": AnswerCoverage.NONE,
        },
        RelevanceLevel.IRRELEVANT: {
            "object_match": MatchLevel.MISMATCH,
            "problem_match": MatchLevel.MISMATCH,
            "constraint_match": ConstraintMatch.MISMATCH,
            "evidence_kind": EvidenceKind.NONE,
            "answer_coverage": AnswerCoverage.NONE,
        },
        RelevanceLevel.UNKNOWN: {
            "object_match": MatchLevel.PARTIAL,
            "problem_match": MatchLevel.PARTIAL,
            "constraint_match": ConstraintMatch.PARTIAL,
            "evidence_kind": EvidenceKind.UNKNOWN,
            "answer_coverage": AnswerCoverage.NONE,
        },
    }
    return PaperAssessment(
        source_id=source_id,
        **factor_sets[relevance],
        supported_aspects=(
            "The evaluated method and reported outcome."
            if relevance in {RelevanceLevel.DIRECT, RelevanceLevel.PARTIAL}
            else None
        ),
        limitations="Only the abstract was available for assessment.",
    )


class ResearcherSchemaTests(unittest.TestCase):
    def test_search_plan_accepts_one_to_five_distinct_queries(self) -> None:
        plan = SearchPlanOutput(
            queries=["retrieval factuality", "RAG verification"]
        )

        self.assertEqual(len(plan.queries), 2)

        with self.assertRaises(ValidationError):
            SearchPlanOutput(queries=[f"query {index}" for index in range(6)])
        with self.assertRaises(ValidationError):
            SearchPlanOutput(
                queries=["RAG verification", " rag   VERIFICATION "]
            )

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

    def test_relevance_is_derived_and_read_only(self) -> None:
        paper = assessment(relevance=RelevanceLevel.PARTIAL)

        self.assertIs(paper.relevance, RelevanceLevel.PARTIAL)
        self.assertNotIn(
            "relevance",
            PaperAssessment.model_json_schema()["properties"],
        )

        with self.assertRaises(ValidationError):
            PaperAssessment(
                source_id="2401.00001",
                relevance=RelevanceLevel.DIRECT,
                object_match=MatchLevel.FULL,
                problem_match=MatchLevel.FULL,
                constraint_match=ConstraintMatch.FULL,
                evidence_kind=EvidenceKind.ANSWER_BEARING,
                answer_coverage=AnswerCoverage.FULL,
                supported_aspects="The reported outcome.",
                limitations="Only the abstract was assessed.",
            )

    def test_unusable_evidence_must_not_claim_supported_aspects(self) -> None:
        with self.assertRaises(ValidationError):
            PaperAssessment(
                source_id="2401.00001",
                object_match=MatchLevel.FULL,
                problem_match=MatchLevel.PARTIAL,
                constraint_match=ConstraintMatch.PARTIAL,
                evidence_kind=EvidenceKind.CONTEXT_ONLY,
                answer_coverage=AnswerCoverage.NONE,
                supported_aspects=(
                    "A claimed answer despite context-only evidence."
                ),
                limitations="The paper only provides background.",
            )

    def test_usable_evidence_requires_supported_aspects(self) -> None:
        with self.assertRaises(ValidationError):
            PaperAssessment(
                source_id="2401.00001",
                object_match=MatchLevel.FULL,
                problem_match=MatchLevel.FULL,
                constraint_match=ConstraintMatch.FULL,
                evidence_kind=EvidenceKind.ANSWER_BEARING,
                answer_coverage=AnswerCoverage.FULL,
                supported_aspects=None,
                limitations="Only the abstract was assessed.",
            )

    def test_unknown_candidate_requires_insufficient_evidence(self) -> None:
        unknown = assessment(relevance=RelevanceLevel.UNKNOWN)
        output = ResearchSynthesisOutput(
            answer=(
                "The abstract lacks enough information to answer the question."
            ),
            evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
            evidence_reason=(
                "The candidate cannot be classified from its abstract."
            ),
            used_source_ids=[],
            assessments=[unknown],
        )

        self.assertIs(output.assessments[0].relevance, RelevanceLevel.UNKNOWN)

        with self.assertRaises(ValidationError):
            ResearchSynthesisOutput(
                answer="No relevant evidence exists.",
                evidence_status=EvidenceStatus.NO_RELEVANT_SOURCES,
                evidence_reason="The candidate could not be classified.",
                used_source_ids=[],
                assessments=[unknown],
            )

        with self.assertRaises(ValidationError):
            ResearchSynthesisOutput(
                answer="The unknown paper supports the answer.",
                evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
                evidence_reason="The abstract is incomplete.",
                used_source_ids=[unknown.source_id],
                assessments=[unknown],
            )

    def test_no_relevant_sources_rejects_relevant_assessment(self) -> None:
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
                evidence_reason=(
                    "The evidence does not fully answer the question."
                ),
                used_source_ids=[],
                assessments=[assessment(relevance=RelevanceLevel.PARTIAL)],
            )

    def test_insufficient_evidence_keeps_source_and_reason(self) -> None:
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
