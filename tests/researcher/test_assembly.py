"""Verify Researcher evidence validation and domain assembly."""

import unittest

from citeguard.domain.research import (
    AnswerRequirement,
    EvidenceStatus,
    SubQuestion,
    SubQuestionStatus,
)
from citeguard.researcher.arxiv import ArxivPaper
from citeguard.researcher.assembly import (
    assemble_insufficient_result,
    assemble_supported_result,
    validate_evidence_analysis,
)
from citeguard.researcher.relevance import (
    AnswerCoverage,
    ConstraintMatch,
    EvidenceKind,
    MatchLevel,
)
from citeguard.researcher.schemas import (
    ClaimSupport,
    EvidenceAnalysisOutput,
    EvidenceGroupAssessment,
    GeneratedClaim,
    GroupSupport,
    PaperAssessment,
)


class ResearcherAssemblyTests(unittest.TestCase):
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
    def _paper(source_id: str = "2401.00001") -> ArxivPaper:
        return ArxivPaper(
            title="Retrieval and factuality",
            source_id=source_id,
            summary="The abstract reports a controlled evaluation.",
            url=f"https://arxiv.org/abs/{source_id}",
        )

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
            answer_coverage=AnswerCoverage.FULL,
            supported_aspects="The method and factuality outcome.",
            limitations="Evidence is limited to the abstract.",
        )

    def test_validates_and_assigns_project_claim_ids(self) -> None:
        output = EvidenceAnalysisOutput(
            assessments=[self._assessment()],
            claims=[
                GeneratedClaim(
                    statement="Retrieval improved factuality.",
                    requirement_ids=["req-001"],
                    candidate_source_ids=["2401.00001"],
                )
            ],
            unmet_requirement_ids=[],
        )

        claims = validate_evidence_analysis(
            output,
            [self._paper()],
            self._subquestion(),
        )

        self.assertEqual(claims[0].id, "claim-001")

    def test_rejects_unknown_requirement_id(self) -> None:
        output = EvidenceAnalysisOutput(
            assessments=[self._assessment()],
            claims=[
                GeneratedClaim(
                    statement="Retrieval improved factuality.",
                    requirement_ids=["req-999"],
                    candidate_source_ids=["2401.00001"],
                )
            ],
            unmet_requirement_ids=["req-001"],
        )

        with self.assertRaisesRegex(ValueError, "unknown"):
            validate_evidence_analysis(
                output,
                [self._paper()],
                self._subquestion(),
            )

    def test_assembles_supported_minimal_group(self) -> None:
        output = EvidenceAnalysisOutput(
            assessments=[self._assessment()],
            claims=[
                GeneratedClaim(
                    statement="Retrieval improved factuality.",
                    requirement_ids=["req-001"],
                    candidate_source_ids=["2401.00001"],
                )
            ],
            unmet_requirement_ids=[],
        )
        claims = validate_evidence_analysis(
            output,
            [self._paper()],
            self._subquestion(),
        )
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

        result = assemble_supported_result(
            claims=claims,
            group=group,
            assessments=output.assessments,
            candidates=[self._paper()],
        )

        self.assertIs(result.evidence_status, EvidenceStatus.SUPPORTED)
        self.assertEqual(result.sources[0].abstract, self._paper().summary)

    def test_insufficient_result_has_no_evidence_group(self) -> None:
        result = assemble_insufficient_result(
            claims=[],
            unmet_requirement_ids=["req-001"],
            assessments=[],
            candidates=[],
        )

        self.assertIsNone(result.evidence_group)
        self.assertIn("req-001", result.evidence_reason)


if __name__ == "__main__":
    unittest.main()
