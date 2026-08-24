"""Verify shared research-domain evidence-state invariants."""

import unittest

from citeguard.domain.research import (
    EvidenceStatus,
    ResearchResult,
    ResearchSource,
)


class ResearchResultTests(unittest.TestCase):
    @staticmethod
    def _source() -> ResearchSource:
        return ResearchSource(
            title="A relevant paper",
            url="https://arxiv.org/abs/2401.00001",
            supported_aspects="The evaluated method and reported outcome.",
            limitations="Only the abstract was evaluated.",
            source_id="2401.00001",
            summary="The abstract provides partial evidence.",
        )

    def test_supported_result_requires_sources_and_no_reason(self) -> None:
        result = ResearchResult(
            answer="The paper supports the conclusion.",
            evidence_status=EvidenceStatus.SUPPORTED,
            sources=[self._source()],
        )

        self.assertIsNone(result.evidence_reason)

        with self.assertRaisesRegex(ValueError, "at least one source"):
            ResearchResult(
                answer="Unsupported claim.",
                evidence_status=EvidenceStatus.SUPPORTED,
            )

    def test_source_requires_support_and_limitation_explanations(self) -> None:
        with self.assertRaisesRegex(ValueError, "supported_aspects"):
            ResearchSource(
                title="A paper",
                url="https://arxiv.org/abs/2401.00001",
                supported_aspects="  ",
                limitations="Only the abstract was evaluated.",
            )

    def test_no_relevant_sources_requires_explanation_and_no_sources(self) -> None:
        result = ResearchResult(
            answer="No relevant arXiv evidence was found.",
            evidence_status=EvidenceStatus.NO_RELEVANT_SOURCES,
            evidence_reason="The candidates addressed a different population.",
        )

        self.assertEqual(result.sources, [])

        with self.assertRaisesRegex(ValueError, "must not contain sources"):
            ResearchResult(
                answer="No relevant evidence was found.",
                evidence_status=EvidenceStatus.NO_RELEVANT_SOURCES,
                sources=[self._source()],
                evidence_reason="The source was not relevant.",
            )

    def test_insufficient_evidence_keeps_partial_sources_and_reason(self) -> None:
        result = ResearchResult(
            answer="The available abstract supports only part of the question.",
            evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
            sources=[self._source()],
            evidence_reason="No candidate evaluates the required setting.",
        )

        self.assertEqual(result.sources[0].source_id, "2401.00001")

        with self.assertRaisesRegex(ValueError, "partial source"):
            ResearchResult(
                answer="Evidence is incomplete.",
                evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
                evidence_reason="No usable paper was retained.",
            )


if __name__ == "__main__":
    unittest.main()
