from datetime import timedelta

from arxiv_models import ArxivQueryResult, ArxivSearchInput
from temporalio import workflow


@workflow.defn
class ArxivSearchWorkflow:
    @workflow.run
    async def run(self, input: ArxivSearchInput) -> list[ArxivQueryResult]:
        return await workflow.execute_activity(
            "search_arxiv_batch",
            input,
            result_type=list[ArxivQueryResult],
            # 表示单次 Activity 尝试的最长执行时间，从 Worker 开始执行 Activity 时计时
            # 如果超过 60 秒，Temporal 将这一次尝试判定为超时。
            # 因为 Activity 默认允许重试，之后可能启动第二次尝试
            start_to_close_timeout=timedelta(seconds=60),
            # 表示整个 Activity 从被 Workflow 调度开始，到最终成功或失败为止，最多允许 5 分钟。
            # 它包括：
            # 在 Task Queue 中排队的时间
            # 每一次 Activity 执行时间
            # 多次重试之间的退避等待时间
            # 一旦总时间达到 5 分钟，即使还可以继续重试，Temporal 也会停止并返回 Activity 超时
            schedule_to_close_timeout=timedelta(minutes=5),
        )
