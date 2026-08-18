import asyncio
import uuid

from arxiv_models import ArxivSearchInput
from arxiv_worker import TASK_QUEUE
from arxiv_workflow import ArxivSearchWorkflow
from temporalio.client import Client


async def main() -> None:
    client = await Client.connect("localhost:7233")

    workflow_id = f"arxiv-search-{uuid.uuid4()}"

    print(f"正在启动 workflow: {workflow_id}")

    results = await client.execute_workflow(
        ArxivSearchWorkflow.run,
        ArxivSearchInput(
            queries=[
                "LLM Reasoning",
                "RAG Verification",
            ],
            max_results=2,
        ),
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )

    for result in results:
        print(f"\n查询主题: {result.query}")

        for paper in result.papers:
            print(f"- {paper.title}")
            print(f"  arXiv ID: {paper.arxiv_id}")
            print(f"  URL: {paper.url}")


if __name__ == "__main__":
    asyncio.run(main())
