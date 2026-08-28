"""Verify the production Worker registers the complete minimal pipeline."""

import unittest

from citeguard.infrastructure.temporal import TEMPORAL_TASK_QUEUE
from citeguard.planner.activity import plan_research
from citeguard.researcher.activity import research_sub_question
from citeguard.verifier.activity import verify_written_report
from citeguard.worker import ACTIVITIES, WORKFLOWS
from citeguard.writer.activity import write_report
from citeguard.workflows.citeguard_workflow import CiteGuardWorkflow


class WorkerRegistrationTests(unittest.TestCase):
    def test_registers_workflow_and_every_activity(self) -> None:
        self.assertEqual(WORKFLOWS, [CiteGuardWorkflow])
        self.assertEqual(
            ACTIVITIES,
            [
                plan_research,
                research_sub_question,
                write_report,
                verify_written_report,
            ],
        )
        self.assertTrue(TEMPORAL_TASK_QUEUE.strip())


if __name__ == "__main__":
    unittest.main()
