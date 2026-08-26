"""Verify deterministic relevance classification from semantic factors."""

import unittest

from citeguard.researcher.relevance import (
    AnswerCoverage,
    ConstraintMatch,
    EvidenceKind,
    MatchLevel,
    RelevanceLevel,
    derive_relevance,
)


class RelevanceDerivationTests(unittest.TestCase):
    def test_full_answer_bearing_match_is_direct(self) -> None:
        relevance = derive_relevance(
            object_match=MatchLevel.FULL,
            problem_match=MatchLevel.FULL,
            constraint_match=ConstraintMatch.FULL,
            evidence_kind=EvidenceKind.ANSWER_BEARING,
            answer_coverage=AnswerCoverage.FULL,
        )

        self.assertIs(relevance, RelevanceLevel.DIRECT)

    def test_absent_explicit_constraints_can_still_be_direct(self) -> None:
        relevance = derive_relevance(
            object_match=MatchLevel.FULL,
            problem_match=MatchLevel.FULL,
            constraint_match=ConstraintMatch.NOT_APPLICABLE,
            evidence_kind=EvidenceKind.ANSWER_BEARING,
            answer_coverage=AnswerCoverage.FULL,
        )

        self.assertIs(relevance, RelevanceLevel.DIRECT)

    def test_real_support_with_incomplete_constraints_is_partial(self) -> None:
        relevance = derive_relevance(
            object_match=MatchLevel.FULL,
            problem_match=MatchLevel.FULL,
            constraint_match=ConstraintMatch.PARTIAL,
            evidence_kind=EvidenceKind.ANSWER_BEARING,
            answer_coverage=AnswerCoverage.PARTIAL,
        )

        self.assertIs(relevance, RelevanceLevel.PARTIAL)

    def test_context_without_answer_coverage_is_background(self) -> None:
        relevance = derive_relevance(
            object_match=MatchLevel.FULL,
            problem_match=MatchLevel.PARTIAL,
            constraint_match=ConstraintMatch.PARTIAL,
            evidence_kind=EvidenceKind.CONTEXT_ONLY,
            answer_coverage=AnswerCoverage.NONE,
        )

        self.assertIs(relevance, RelevanceLevel.BACKGROUND)

    def test_object_mismatch_without_evidence_is_irrelevant(self) -> None:
        relevance = derive_relevance(
            object_match=MatchLevel.MISMATCH,
            problem_match=MatchLevel.MISMATCH,
            constraint_match=ConstraintMatch.MISMATCH,
            evidence_kind=EvidenceKind.NONE,
            answer_coverage=AnswerCoverage.NONE,
        )

        self.assertIs(relevance, RelevanceLevel.IRRELEVANT)

    def test_matching_topic_without_evidence_is_irrelevant(self) -> None:
        relevance = derive_relevance(
            object_match=MatchLevel.FULL,
            problem_match=MatchLevel.FULL,
            constraint_match=ConstraintMatch.FULL,
            evidence_kind=EvidenceKind.NONE,
            answer_coverage=AnswerCoverage.NONE,
        )

        self.assertIs(relevance, RelevanceLevel.IRRELEVANT)

    def test_insufficient_abstract_information_is_unknown(self) -> None:
        relevance = derive_relevance(
            object_match=MatchLevel.PARTIAL,
            problem_match=MatchLevel.PARTIAL,
            constraint_match=ConstraintMatch.PARTIAL,
            evidence_kind=EvidenceKind.UNKNOWN,
            answer_coverage=AnswerCoverage.NONE,
        )

        self.assertIs(relevance, RelevanceLevel.UNKNOWN)

    def test_inconsistent_factors_fail_instead_of_falling_back(self) -> None:
        with self.assertRaisesRegex(ValueError, "mismatch"):
            derive_relevance(
                object_match=MatchLevel.MISMATCH,
                problem_match=MatchLevel.FULL,
                constraint_match=ConstraintMatch.FULL,
                evidence_kind=EvidenceKind.ANSWER_BEARING,
                answer_coverage=AnswerCoverage.FULL,
            )

        with self.assertRaisesRegex(ValueError, "context-only"):
            derive_relevance(
                object_match=MatchLevel.FULL,
                problem_match=MatchLevel.FULL,
                constraint_match=ConstraintMatch.FULL,
                evidence_kind=EvidenceKind.CONTEXT_ONLY,
                answer_coverage=AnswerCoverage.PARTIAL,
            )

        with self.assertRaisesRegex(ValueError, "answer-bearing"):
            derive_relevance(
                object_match=MatchLevel.FULL,
                problem_match=MatchLevel.FULL,
                constraint_match=ConstraintMatch.FULL,
                evidence_kind=EvidenceKind.ANSWER_BEARING,
                answer_coverage=AnswerCoverage.NONE,
            )

        with self.assertRaisesRegex(ValueError, "unknown"):
            derive_relevance(
                object_match=MatchLevel.FULL,
                problem_match=MatchLevel.FULL,
                constraint_match=ConstraintMatch.FULL,
                evidence_kind=EvidenceKind.UNKNOWN,
                answer_coverage=AnswerCoverage.PARTIAL,
            )


if __name__ == "__main__":
    unittest.main()
