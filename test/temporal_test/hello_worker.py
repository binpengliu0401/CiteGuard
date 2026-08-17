import asyncio

from hello_workflow import DurableHelloWorkflow
from temporalio.client import Client
from temporalio.worker import Worker

TASK_QUEUE = "citeguard-temporal-spike"


async def main() -> None:
    # 连接localhost 7233
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        # 监听citeguard-temporal-spike Task Queue
        task_queue=TASK_QUEUE,
        # 注册 DurableHelloWorkflow
        workflows=[DurableHelloWorkflow],
    )

    print(f"Worker 正在监听 Task Queue: {TASK_QUEUE}")
    # 持续等待和执行 Workflow Task
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
