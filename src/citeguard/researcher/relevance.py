"""Deterministically derive paper relevance from factorized judgments."""

from enum import Enum


class MatchLevel(str, Enum):
    """How completely a candidate matches one required research dimension."""

    FULL = "full"
    PARTIAL = "partial"
    MISMATCH = "mismatch"


class ConstraintMatch(str, Enum):
    """How well explicit population, setting, method, and time match."""

    FULL = "full"
    PARTIAL = "partial"
    MISMATCH = "mismatch"
    NOT_APPLICABLE = "not_applicable"


class EvidenceKind(str, Enum):
    """Whether the abstract contains classifiable subquestion evidence."""

    ANSWER_BEARING = "answer_bearing"
    CONTEXT_ONLY = "context_only"
    NONE = "none"
    UNKNOWN = "unknown"


class AnswerCoverage(str, Enum):
    """How much of the exact subquestion the abstract-level evidence covers."""

    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"


class RelevanceLevel(str, Enum):
    """How directly one candidate paper can support the exact subquestion."""

    DIRECT = "direct"
    PARTIAL = "partial"
    BACKGROUND = "background"
    IRRELEVANT = "irrelevant"
    UNKNOWN = "unknown"


def derive_relevance(
    *,
    object_match: MatchLevel,
    problem_match: MatchLevel,
    constraint_match: ConstraintMatch,
    evidence_kind: EvidenceKind,
    answer_coverage: AnswerCoverage,
) -> RelevanceLevel:
    """Map observable assessment factors to one relevance label.

    The model judges semantic factors, while this function owns the stable
    classification policy. Inconsistent factors fail instead of being coerced
    into an apparently successful label.

    Args:
        object_match: Match between the paper and the research object.
        problem_match: Match between the paper's problem and the subquestion.
        constraint_match: Coverage of explicit population, setting, method,
            time, and other constraints.
        evidence_kind: Whether the abstract contains an answer-bearing result,
            contextual material only, no relevant evidence, or too little
            information to classify.
        answer_coverage: Amount of the exact subquestion supported by the
            abstract-level evidence.

    Returns:
        A deterministic relevance label, or unknown when classification must
        abstain because the abstract is insufficient.

    Raises:
        ValueError: If the factors express mutually inconsistent evidence.
    """

    if evidence_kind is EvidenceKind.UNKNOWN:
        if answer_coverage is not AnswerCoverage.NONE:
            raise ValueError("unknown evidence requires no answer coverage")
        return RelevanceLevel.UNKNOWN

    if (
        object_match is MatchLevel.MISMATCH
        or problem_match is MatchLevel.MISMATCH
    ):
        if (
            evidence_kind is not EvidenceKind.NONE
            or answer_coverage is not AnswerCoverage.NONE
        ):
            raise ValueError(
                "object or problem mismatch requires no subquestion evidence"
            )
        return RelevanceLevel.IRRELEVANT

    if evidence_kind is EvidenceKind.NONE:
        if answer_coverage is not AnswerCoverage.NONE:
            raise ValueError("no evidence requires no answer coverage")
        return RelevanceLevel.IRRELEVANT

    if evidence_kind is EvidenceKind.CONTEXT_ONLY:
        if answer_coverage is not AnswerCoverage.NONE:
            raise ValueError(
                "context-only evidence requires no answer coverage"
            )
        return RelevanceLevel.BACKGROUND

    if answer_coverage is AnswerCoverage.NONE:
        raise ValueError("answer-bearing evidence requires answer coverage")

    if (
        object_match is MatchLevel.FULL
        and problem_match is MatchLevel.FULL
        and constraint_match
        in {ConstraintMatch.FULL, ConstraintMatch.NOT_APPLICABLE}
        and answer_coverage is AnswerCoverage.FULL
    ):
        return RelevanceLevel.DIRECT

    return RelevanceLevel.PARTIAL
