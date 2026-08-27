"""Verify bottom-up minimal evidence group search."""

import unittest

from citeguard.researcher.meg import (
    ClaimCandidate,
    MEG_BATCH_SIZE,
    find_minimal_evidence_groups,
)
from citeguard.researcher.schemas import (
    ClaimSupport,
    EvidenceGroupAssessment,
    GroupSupport,
)


class MinimalEvidenceGroupTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _claims() -> list[ClaimCandidate]:
        return [
            ClaimCandidate(
                id="claim-001",
                statement="Heuristic writing was used.",
                requirement_ids=["req-001"],
                candidate_source_ids=["paper-a"],
            ),
            ClaimCandidate(
                id="claim-002",
                statement="Learned writing policies were introduced.",
                requirement_ids=["req-002"],
                candidate_source_ids=["paper-b", "paper-c"],
            ),
        ]

    async def test_finds_two_source_group_and_prunes_singletons(self) -> None:
        observed: list[list[tuple[str, ...]]] = []

        async def predictor(
            groups: list[tuple[str, ...]],
        ) -> list[EvidenceGroupAssessment]:
            observed.append(groups)
            return [
                EvidenceGroupAssessment(
                    source_ids=list(group),
                    support=GroupSupport.FULL,
                    claim_support=[
                        ClaimSupport(
                            claim_id="claim-001",
                            source_ids=["paper-a"],
                        ),
                        ClaimSupport(
                            claim_id="claim-002",
                            source_ids=[
                                source_id
                                for source_id in group
                                if source_id != "paper-a"
                            ],
                        ),
                    ],
                    missing_claim_ids=[],
                    missing_requirement_ids=[],
                )
                for group in groups
            ]

        results = await find_minimal_evidence_groups(
            claims=self._claims(),
            requirement_ids=["req-001", "req-002"],
            support_predictor=predictor,
        )

        self.assertEqual(observed[0], [("paper-a", "paper-b"),
                                       ("paper-a", "paper-c")])
        self.assertEqual(len(results), 2)

    async def test_rejects_fabricated_group_output(self) -> None:
        async def predictor(
            groups: list[tuple[str, ...]],
        ) -> list[EvidenceGroupAssessment]:
            return [
                EvidenceGroupAssessment(
                    source_ids=["paper-x", "paper-y"],
                    support=GroupSupport.NONE,
                    claim_support=[],
                    missing_claim_ids=["claim-001", "claim-002"],
                    missing_requirement_ids=["req-001", "req-002"],
                )
            ]

        with self.assertRaisesRegex(ValueError, "exactly match"):
            await find_minimal_evidence_groups(
                claims=self._claims(),
                requirement_ids=["req-001", "req-002"],
                support_predictor=predictor,
            )

    async def test_rejects_swapped_frozen_claim_provenance(self) -> None:
        async def predictor(
            groups: list[tuple[str, ...]],
        ) -> list[EvidenceGroupAssessment]:
            return [
                EvidenceGroupAssessment(
                    source_ids=list(group),
                    support=GroupSupport.FULL,
                    claim_support=[
                        ClaimSupport(
                            claim_id="claim-001",
                            source_ids=["paper-b"],
                        ),
                        ClaimSupport(
                            claim_id="claim-002",
                            source_ids=["paper-a"],
                        ),
                    ],
                    missing_claim_ids=[],
                    missing_requirement_ids=[],
                )
                for group in groups
            ]

        with self.assertRaisesRegex(ValueError, "frozen candidates"):
            await find_minimal_evidence_groups(
                claims=self._claims(),
                requirement_ids=["req-001", "req-002"],
                support_predictor=predictor,
            )

    async def test_batches_one_cardinality_level(self) -> None:
        source_ids = [
            f"paper-{index:02d}"
            for index in range(1, MEG_BATCH_SIZE + 2)
        ]
        claims = [
            ClaimCandidate(
                id="claim-001",
                statement="One source can support the claim.",
                requirement_ids=["req-001"],
                candidate_source_ids=source_ids,
            )
        ]
        observed_sizes: list[int] = []

        async def predictor(
            groups: list[tuple[str, ...]],
        ) -> list[EvidenceGroupAssessment]:
            observed_sizes.append(len(groups))
            if len(observed_sizes) == 1:
                return [
                    EvidenceGroupAssessment(
                        source_ids=list(group),
                        support=GroupSupport.NONE,
                        claim_support=[],
                        missing_claim_ids=["claim-001"],
                        missing_requirement_ids=["req-001"],
                    )
                    for group in groups
                ]
            return [
                EvidenceGroupAssessment(
                    source_ids=list(group),
                    support=GroupSupport.FULL,
                    claim_support=[
                        ClaimSupport(
                            claim_id="claim-001",
                            source_ids=list(group),
                        )
                    ],
                    missing_claim_ids=[],
                    missing_requirement_ids=[],
                )
                for group in groups
            ]

        results = await find_minimal_evidence_groups(
            claims=claims,
            requirement_ids=["req-001"],
            support_predictor=predictor,
        )

        self.assertEqual(observed_sizes, [MEG_BATCH_SIZE, 1])
        self.assertEqual(results[0].source_ids, [source_ids[-1]])

    async def test_returns_empty_when_no_group_is_full(self) -> None:
        async def predictor(
            groups: list[tuple[str, ...]],
        ) -> list[EvidenceGroupAssessment]:
            return [
                EvidenceGroupAssessment(
                    source_ids=list(group),
                    support=GroupSupport.PARTIAL,
                    claim_support=[
                        ClaimSupport(
                            claim_id="claim-001",
                            source_ids=["paper-a"],
                        )
                    ],
                    missing_claim_ids=["claim-002"],
                    missing_requirement_ids=["req-002"],
                )
                for group in groups
            ]

        results = await find_minimal_evidence_groups(
            claims=self._claims(),
            requirement_ids=["req-001", "req-002"],
            support_predictor=predictor,
        )

        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
