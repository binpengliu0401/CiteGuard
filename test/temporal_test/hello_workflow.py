from datetime import timedelta

from temporalio import workflow


@workflow.defn
class DurableHelloWorkflow:
    @workflow.run
    # 接受name
    async def run(self, name: str) -> str:
        # 等待一个20s的持久化timer
        await workflow.sleep(timedelta(seconds=20))
        # 返回hello, name
        return f"Hello, {name}!"
