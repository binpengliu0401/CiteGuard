"""Bottom-up minimal evidence group search for frozen research claims."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from itertools import combinations

from citeguard.researcher.schemas import (
    EvidenceGroupAssessment,
    GeneratedClaim,
    GroupSupport,
)

MEG_BATCH_SIZE = 32


@dataclass(frozen=True)
class ClaimCandidate:
    """One fixed claim with project-owned identity before MEG selection."""

    id: str
    statement: str
    requirement_ids: list[str]
    candidate_source_ids: list[str]


GroupSupportPredictor = Callable[
    [list[tuple[str, ...]]],
    Awaitable[list[EvidenceGroupAssessment]],
]


def prepare_claim_candidates(
    claims: list[GeneratedClaim],
) -> list[ClaimCandidate]:
    """Assign deterministic IDs to model-generated claim statements."""

    return [
        ClaimCandidate(
            id=f"claim-{index:03d}",
            statement=claim.statement,
            requirement_ids=claim.requirement_ids,
            candidate_source_ids=claim.candidate_source_ids,
        )
        for index, claim in enumerate(claims, start=1)
    ]


async def find_minimal_evidence_groups(
    *,
    claims: list[ClaimCandidate],
    requirement_ids: list[str],
    support_predictor: GroupSupportPredictor,
) -> list[EvidenceGroupAssessment]:
    """Find the smallest fully supporting source groups.

    The search enumerates candidate groups by increasing cardinality. It stops
    at the first level containing FULL groups, which makes every returned group
    minimum-cardinality under the supplied support judgments.

    Args:
        claims: Frozen claims and the sources that may support each one.
        requirement_ids: Fixed completeness requirements from Planner.
        support_predictor: Batched semantic judge for one cardinality level.

    Returns:
        FULL groups from the first successful bounded batch at the smallest
        successful cardinality, or an empty list when no combination is full.

    Raises:
        ValueError: If predictor output does not exactly describe the requested
            groups or contains unknown and internally inconsistent provenance.
    """

    if not claims:
        return []

    source_ids = _ordered_candidate_source_ids(claims)
    if not source_ids:
        return []

    for size in range(1, len(source_ids) + 1):
        groups = [
            group
            for group in combinations(source_ids, size)
            if _can_cover_every_claim(group, claims)
        ]
        if not groups:
            continue
        for offset in range(0, len(groups), MEG_BATCH_SIZE):
            batch = groups[offset:offset + MEG_BATCH_SIZE]
            assessments = await support_predictor(batch)
            _validate_level(
                groups=batch,
                assessments=assessments,
                claims=claims,
                requirement_ids=requirement_ids,
            )
            full_groups = [
                item
                for item in assessments
                if item.support is GroupSupport.FULL
            ]
            if full_groups:
                return full_groups

    return []


def _can_cover_every_claim(
    group: tuple[str, ...],
    claims: list[ClaimCandidate],
) -> bool:
    """Prune groups lacking any candidate source for a frozen claim."""

    group_ids = set(group)
    return all(
        group_ids & set(claim.candidate_source_ids)
        for claim in claims
    )


def _ordered_candidate_source_ids(
    claims: list[ClaimCandidate],
) -> list[str]:
    """Collect candidate sources once while preserving claim order."""

    seen: set[str] = set()
    ordered: list[str] = []
    for claim in claims:
        for source_id in claim.candidate_source_ids:
            if source_id not in seen:
                seen.add(source_id)
                ordered.append(source_id)
    return ordered


def _validate_level(
    *,
    groups: list[tuple[str, ...]],
    assessments: list[EvidenceGroupAssessment],
    claims: list[ClaimCandidate],
    requirement_ids: list[str],
) -> None:
    """Validate exact batched output and all group-support references."""

    expected = {frozenset(group) for group in groups}
    actual = {frozenset(item.source_ids) for item in assessments}
    if len(assessments) != len(actual) or actual != expected:
        raise ValueError(
            "group assessments must exactly match requested source groups"
        )

    claims_by_id = {claim.id: claim for claim in claims}
    claim_ids = set(claims_by_id)
    known_requirements = set(requirement_ids)
    for item in assessments:
        group_ids = set(item.source_ids)
        supported_claim_ids = {
            support.claim_id for support in item.claim_support
        }
        if not supported_claim_ids.issubset(claim_ids):
            raise ValueError("group assessment used an unknown claim ID")
        if not set(item.missing_claim_ids).issubset(claim_ids):
            raise ValueError("group assessment missed an unknown claim ID")
        if not set(item.missing_requirement_ids).issubset(
            known_requirements
        ):
            raise ValueError(
                "group assessment used an unknown requirement ID"
            )
        for support in item.claim_support:
            if not set(support.source_ids).issubset(group_ids):
                raise ValueError(
                    "claim support source IDs must belong to the group"
                )
            candidate_ids = set(
                claims_by_id[support.claim_id].candidate_source_ids
            )
            if not set(support.source_ids).issubset(candidate_ids):
                raise ValueError(
                    "claim support source IDs must belong to the claim's "
                    "frozen candidates"
                )

        if item.support is GroupSupport.FULL:
            if supported_claim_ids != claim_ids:
                raise ValueError("full group must support every frozen claim")
            used_ids = {
                source_id
                for support in item.claim_support
                for source_id in support.source_ids
            }
            if used_ids != group_ids:
                raise ValueError(
                    "every source in a full group must support a claim"
                )
