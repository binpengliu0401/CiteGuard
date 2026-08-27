"""Verify shared research-domain evidence and target invariants."""

import unittest

from citeguard.domain.research import (
    AnswerRequirement,
    EvidenceGroup,
    EvidenceStatus,
    ResearchClaim,
    ResearchResult,
    ResearchSource,
    SubQuestion,
    SubQuestionStatus,
)


class ResearchResultTests(unittest.TestCase):
    @staticmethod
    def _source() -> ResearchSource:
        return ResearchSource(
            title="A relevant paper",
            url="https://arxiv.org/abs/2401.00001",
            source_id="2401.00001",
            abstract="The abstract provides direct evidence.",
            supported_aspects="The evaluated method and reported outcome.",
            limitations="Only the abstract was evaluated.",
        )

    @staticmethod
    def _claim() -> ResearchClaim:
        return ResearchClaim(
            id="claim-001",
            statement="The evaluated method improved the reported outcome.",
            source_ids=["2401.00001"],
        )

    def test_supported_result_requires_claims_sources_and_group(self) -> None:
        result = ResearchResult(
            claims=[self._claim()],
            evidence_status=EvidenceStatus.SUPPORTED,
            sources=[self._source()],
            evidence_group=EvidenceGroup(
                source_ids=["2401.00001"]
            ),
        )

        self.assertIsNone(result.evidence_reason)

        with self.assertRaisesRegex(ValueError, "evidence group"):
            ResearchResult(
                claims=[self._claim()],
                evidence_status=EvidenceStatus.SUPPORTED,
                sources=[self._source()],
            )

    def test_source_requires_abstract_and_provenance(self) -> None:
        with self.assertRaisesRegex(ValueError, "abstract"):
            ResearchSource(
                title="A paper",
                url="https://arxiv.org/abs/2401.00001",
                source_id="2401.00001",
                abstract="  ",
                supported_aspects="The method.",
                limitations="Only the abstract was evaluated.",
            )

    def test_no_relevant_sources_has_no_claims_or_sources(self) -> None:
        result = ResearchResult(
            claims=[],
            evidence_status=EvidenceStatus.NO_RELEVANT_SOURCES,
            evidence_reason="The candidates addressed another problem.",
        )

        self.assertEqual(result.sources, [])

        with self.assertRaisesRegex(ValueError, "claims or sources"):
            ResearchResult(
                claims=[self._claim()],
                evidence_status=EvidenceStatus.NO_RELEVANT_SOURCES,
                sources=[self._source()],
                evidence_reason="The source was not relevant.",
            )

    def test_insufficient_evidence_can_keep_partial_claims(self) -> None:
        result = ResearchResult(
            claims=[self._claim()],
            evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
            sources=[self._source()],
            evidence_reason="No source covers the required setting.",
        )

        self.assertIsNone(result.evidence_group)

    def test_subquestion_requires_fixed_answer_contract(self) -> None:
        result = SubQuestion(
            id="sq-001",
            question="How does retrieval affect reliability?",
            primary_answer_target="Retrieval effects on reliability",
            answer_requirements=[
                AnswerRequirement(
                    id="req-001",
                    description="A retrieval method",
                )
            ],
            status=SubQuestionStatus.NEW,
        )

        self.assertEqual(result.answer_requirements[0].id, "req-001")


if __name__ == "__main__":
    unittest.main()
