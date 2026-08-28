"""Command-line client for the formal CiteGuard Workflow."""

import argparse
import asyncio
from uuid import uuid4

from pydantic import TypeAdapter
from temporalio.client import Client

from citeguard.infrastructure.temporal import (
    TEMPORAL_ADDRESS,
    TEMPORAL_DATA_CONVERTER,
    TEMPORAL_TASK_QUEUE,
)
from citeguard.workflows.citeguard_workflow import CiteGuardWorkflow
from citeguard.workflows.contracts import (
    CiteGuardWorkflowInput,
    CiteGuardWorkflowResult,
)


async def run_workflow(
    research_question: str,
    session_id: str,
    workflow_id: str,
) -> CiteGuardWorkflowResult:
    """Execute one Workflow and return its inspectable final result.

    Args:
        research_question: User question sent to Planner.
        session_id: Stable identity for future session-memory lookup.
        workflow_id: Unique Temporal execution identity.

    Returns:
        The complete minimal-pipeline result, including content rejection.

    Side effects:
        Connects to Temporal and starts a Workflow execution.
    """

    client = await Client.connect(
        TEMPORAL_ADDRESS,
        data_converter=TEMPORAL_DATA_CONVERTER,
    )
    return await client.execute_workflow(
        CiteGuardWorkflow.run,
        CiteGuardWorkflowInput(
            research_question=research_question,
            session_id=session_id,
        ),
        id=workflow_id,
        task_queue=TEMPORAL_TASK_QUEUE,
        result_type=CiteGuardWorkflowResult,
    )


def main() -> None:
    """Parse command-line input, execute the Workflow, and print JSON."""

    parser = argparse.ArgumentParser()
    parser.add_argument("research_question")
    parser.add_argument("--session-id", default="local-session")
    parser.add_argument(
        "--workflow-id",
        default=f"citeguard-{uuid4()}",
    )
    args = parser.parse_args()
    result = asyncio.run(
        run_workflow(
            args.research_question,
            args.session_id,
            args.workflow_id,
        )
    )
    adapter = TypeAdapter(CiteGuardWorkflowResult)
    print(adapter.dump_json(result, indent=2).decode())


if __name__ == "__main__":
    main()
