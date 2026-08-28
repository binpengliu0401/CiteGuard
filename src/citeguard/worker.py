"""Production Worker registration for the formal CiteGuard pipeline."""

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from citeguard.infrastructure.temporal import (
    TEMPORAL_ADDRESS,
    TEMPORAL_DATA_CONVERTER,
    TEMPORAL_TASK_QUEUE,
    TEMPORAL_WORKFLOW_RUNNER,
)
from citeguard.planner.activity import plan_research
from citeguard.researcher.activity import research_sub_question
from citeguard.verifier.activity import verify_written_report
from citeguard.writer.activity import write_report
from citeguard.workflows.citeguard_workflow import CiteGuardWorkflow

WORKFLOWS = [CiteGuardWorkflow]
ACTIVITIES = [
    plan_research,
    research_sub_question,
    write_report,
    verify_written_report,
]


async def run_worker() -> None:
    """Connect to Temporal and serve every formal pipeline boundary.

    Side effects:
        Opens a Temporal connection and polls the configured task queue until
        the process is cancelled.
    """

    client = await Client.connect(
        TEMPORAL_ADDRESS,
        data_converter=TEMPORAL_DATA_CONVERTER,
    )
    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=WORKFLOWS,
        activities=ACTIVITIES,
        workflow_runner=TEMPORAL_WORKFLOW_RUNNER,
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
