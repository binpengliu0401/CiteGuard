"""Verify deterministic Writer report assembly."""

import unittest

from citeguard.domain.research import EvidenceStatus
from citeguard.writer.assembly import assemble_report
from citeguard.writer.contracts import WriterInput
from tests.writer.helpers import (
    insufficient_item,
    no_relevant_item,
    supported_item,
)


class WriterAssemblyTests(unittest.TestCase):
    def test_one_claim_becomes_one_attributable_statement(self) -> None:
        item = supported_item("sq-001", "claim-001", "source-001")

        report = assemble_report(
            WriterInput(
                research_question="What is the supported finding?",
                research_results=[item],
            )
        )

        self.assertEqual(
            report.research_question,
            "What is the supported finding?",
        )
        self.assertEqual(len(report.sections), 1)
        statement = report.sections[0].statements[0]
        self.assertEqual(statement.id, "statement-001")
        self.assertEqual(statement.text, item.result.claims[0].statement)
        self.assertEqual(statement.sub_question_id, "sq-001")
        self.assertEqual(statement.claim_ids, ["claim-001"])
        self.assertEqual(statement.source_ids, ["source-001"])

    def test_preserves_order_scope_and_repeated_local_claim_ids(self) -> None:
        first = supported_item("sq-first", "claim-001", "source-first")
        second = supported_item(
            "sq-second",
            "claim-001",
            "source-second",
        )
        empty = no_relevant_item("sq-empty")

        report = assemble_report(
            WriterInput(
                research_question="Compare three evidence scopes.",
                research_results=[first, second, empty],
            )
        )

        self.assertEqual(
            [section.sub_question_id for section in report.sections],
            ["sq-first", "sq-second", "sq-empty"],
        )
        self.assertEqual(
            [
                statement.id
                for section in report.sections
                for statement in section.statements
            ],
            ["statement-001", "statement-002"],
        )
        self.assertEqual(
            report.sections[0].statements[0].claim_ids,
            ["claim-001"],
        )
        self.assertEqual(
            report.sections[1].statements[0].claim_ids,
            ["claim-001"],
        )
        self.assertEqual(report.sections[2].statements, [])
        self.assertIs(
            report.sections[2].evidence_status,
            EvidenceStatus.NO_RELEVANT_SOURCES,
        )
        self.assertEqual(
            report.sections[2].evidence_reason,
            "No relevant abstract was found.",
        )

    def test_preserves_partial_state_and_distinct_limitations(self) -> None:
        first = supported_item(
            "sq-supported",
            "claim-001",
            "source-supported",
            limitation="One synthetic setting was evaluated.",
        )
        duplicate = supported_item(
            "sq-duplicate",
            "claim-001",
            "source-duplicate",
            limitation="  ONE synthetic setting was evaluated. ",
        )
        partial = insufficient_item("sq-partial")

        report = assemble_report(
            WriterInput(
                research_question="Summarize supported and partial evidence.",
                research_results=[first, duplicate, partial],
            )
        )

        self.assertIs(
            report.sections[2].evidence_status,
            EvidenceStatus.INSUFFICIENT_EVIDENCE,
        )
        self.assertEqual(
            report.sections[2].evidence_reason,
            "The required second setting was not evaluated.",
        )
        self.assertEqual(
            report.limitations,
            [
                "One synthetic setting was evaluated.",
                "Other settings were not evaluated.",
            ],
        )


if __name__ == "__main__":
    unittest.main()
