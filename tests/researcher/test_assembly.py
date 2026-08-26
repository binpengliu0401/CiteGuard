"""Verify deterministic Researcher schema-to-domain assembly."""

import unittest

from citeguard.domain.research import EvidenceStatus
from citeguard.researcher.arxiv import ArxivPaper
from citeguard.researcher.assembly import assemble_research_result
from citeguard.researcher.relevance import (
    AnswerCoverage,
    ConstraintMatch,
    EvidenceKind,
    MatchLevel,
)
from citeguard.researcher.schemas import (
    PaperAssessment,
    ResearchSynthesisOutput,
)


class ResearcherAssemblyTests(unittest.TestCase):
    @staticmethod
    def _paper(source_id: str = "2401.00001") -> ArxivPaper:
        return ArxivPaper(
            title="Retrieval and factuality",
            source_id=source_id,
            summary="The abstract reports a controlled evaluation.",
            url=f"https://arxiv.org/abs/{source_id}",
        )

    @staticmethod
    def _assessment(source_id: str = "2401.00001") -> PaperAssessment:
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

    def test_maps_only_used_candidate_ids_to_domain_sources(self) -> None:
        output = ResearchSynthesisOutput(
            answer="Retrieval improved factuality in the reported evaluation.",
            evidence_status=EvidenceStatus.SUPPORTED,
            evidence_reason=None,
            used_source_ids=["2401.00001"],
            assessments=[self._assessment()],
        )

        result = assemble_research_result(output, [self._paper()])

        self.assertEqual(result.sources[0].title, "Retrieval and factuality")
        self.assertEqual(result.sources[0].source_id, "2401.00001")
        self.assertEqual(
            result.sources[0].supported_aspects,
            "The method and factuality outcome.",
        )
        self.assertEqual(
            result.sources[0].limitations,
            "Evidence is limited to the abstract.",
        )

    def test_requires_an_assessment_for_every_candidate(self) -> None:
        output = ResearchSynthesisOutput(
            answer="Retrieval improved factuality.",
            evidence_status=EvidenceStatus.SUPPORTED,
            evidence_reason=None,
            used_source_ids=["2401.00001"],
            assessments=[self._assessment()],
        )

        with self.assertRaisesRegex(ValueError, "exactly match"):
            assemble_research_result(
                output,
                [self._paper(), self._paper("2401.00002")],
            )


if __name__ == "__main__":
    unittest.main()
