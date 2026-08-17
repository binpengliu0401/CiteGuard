import asyncio
import uuid

from hello_worker import TASK_QUEUE
from hello_workflow import DurableHelloWorkflow
from temporalio.client import Client


async def main() -> None:
    # 连接Temporal server
    client = await Client.connect("localhost:7233")
    # 使用 UUID 创建唯一 Workflow ID
    workflow_id = f"durable-hello-{uuid.uuid4()}"

    print(f"正在启动 workflow: {workflow_id}")
    # 向指定 Task Queue 启动 Workflow
    result = await client.execute_workflow(
        DurableHelloWorkflow.run,
        "CiteGuard",
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )

    print(f"Workflow 执行结果: {result}")


if __name__ == "__main__":
    asyncio.run(main())
