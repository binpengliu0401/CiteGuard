"""Verify the deterministic Writer Temporal Activity boundary."""

import unittest

from citeguard.writer.activity import write_report
from citeguard.writer.contracts import WriterInput
from tests.writer.helpers import supported_item


class WriterActivityTests(unittest.IsolatedAsyncioTestCase):
    async def test_activity_returns_the_deterministic_report(self) -> None:
        writer_input = WriterInput(
            research_question="What is the supported finding?",
            research_results=[
                supported_item("sq-001", "claim-001", "source-001")
            ],
        )

        report = await write_report(writer_input)

        self.assertEqual(
            report.research_question,
            "What is the supported finding?",
        )
        self.assertEqual(report.sections[0].sub_question_id, "sq-001")
        self.assertEqual(
            report.sections[0].statements[0].source_ids,
            ["source-001"],
        )


if __name__ == "__main__":
    unittest.main()
