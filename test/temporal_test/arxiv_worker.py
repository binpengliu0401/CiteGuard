import asyncio

from arxiv_activity import search_arxiv_batch
from arxiv_workflow import ArxivSearchWorkflow
from temporalio.client import Client
from temporalio.worker import Worker

TASK_QUEUE = "citeguard-arxiv-search"


async def main() -> None:
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ArxivSearchWorkflow],
        activities=[search_arxiv_batch],
    )

    print(f"Worker正在监听 Task Queue: {TASK_QUEUE}")

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
