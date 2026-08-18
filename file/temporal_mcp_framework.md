# Temporal 与 MCP 当前 Spike 设计

> 状态：基础调用链已实现
> 更新日期：2026-08-18
> 当前目标：本阶段任务已完成

## 1. 当前任务

仓库已经分别验证了两件事：

- `test/temporal_test` 中的 Temporal Workflow 可以运行和持久等待；
- `test/mcp_test` 中的 MCP Client 可以通过 stdio 启动 MCP Server，并发查询 arXiv。

目前已经把这两个 spike 接通：

```text
Temporal Workflow
    → 调度 Activity
    → Activity 执行已有 MCP 调用
    → MCP Server 查询 arXiv
    → Activity 返回结果
    → Workflow 返回结果
```

当前阶段已经实现这条最小链路，不提前设计完整的生产框架。

## 2. 为什么 MCP 调用必须放进 Activity

Temporal Workflow 会根据 Event History 进行 replay。同一个 Workflow 在重放时，必须产生与原来相同的 Temporal 命令。

Workflow 适合执行：

- 根据输入决定调用哪个 Activity；
- 按顺序或并行调度 Activity；
- 等待 Activity 结果；
- 对结果做简单、确定性的数据整理；
- 使用 Temporal 提供的 timer。

Workflow 不应直接执行：

- MCP 或 HTTP 请求；
- 启动 MCP Server 子进程；
- 读写文件；
- 读取可能变化的外部状态；
- 使用普通的当前时间、随机数或 UUID 决定执行路径。

当前 `arxiv_client.py` 会启动子进程、建立 stdio 连接并调用外部服务，因此这部分属于 Activity。

Activity 不需要满足 Workflow 的确定性约束。Activity 成功返回后，结果会记录到 Temporal Event History；Workflow replay 时读取历史结果，不会重新执行已经确认完成的 MCP 调用。

## 3. 当前 Activity 边界

第一版使用一个批量查询 Activity：

```text
search_arxiv_batch
  输入：queries、max_results
  过程：
    1. 启动当前 arXiv MCP Server
    2. 建立 stdio ClientSession
    3. 完成 MCP client 初始化
    4. 并发调用 search_arxiv
    5. 整理 MCP 返回结果
    6. 关闭 session 和子进程
  输出：每个 query 对应的论文结果
```

暂时不采用“一条 query 一个 Activity”，因为当前使用 stdio transport，每个 Activity 都独立启动 MCP Server 会增加不必要的子进程开销。先保持现有 `arxiv_client.py` 的“一次连接、并发多个 query”调用方式，只把整体搬进 Activity。

如果后续实际运行发现批量 Activity 的失败隔离不够，再根据测试结果调整粒度。

## 4. 输入输出

Activity 输入只包含调用所需的数据，例如：

```python
@dataclass
class ArxivSearchInput:
    queries: list[str]
    max_results: int = 3
```

Activity 返回普通、可序列化的数据，不直接返回 MCP SDK 的 `CallToolResult` 或 `TextContent`：

```python
@dataclass
class ArxivPaper:
    title: str
    arxiv_id: str
    summary: str
    url: str


@dataclass
class ArxivQueryResult:
    query: str
    papers: list[ArxivPaper]
```

这样 Workflow 只处理项目自己的数据结构，不需要理解 MCP session 和返回对象。

## 5. Workflow、Activity 和 Worker 的关系

Workflow 只调度 Activity：

```python
@workflow.defn
class ArxivSearchWorkflow:
    @workflow.run
    async def run(self, input: ArxivSearchInput):
        return await workflow.execute_activity(
            "search_arxiv_batch",
            input,
            start_to_close_timeout=timedelta(seconds=60),
            schedule_to_close_timeout=timedelta(minutes=5),
        )
```

Activity 包装当前 MCP Client 逻辑：

```python
@activity.defn(name="search_arxiv_batch")
async def search_arxiv_batch(input: ArxivSearchInput):
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # 并发执行 input.queries 中的 search_arxiv 调用
            # 把 MCP 返回值转换为 ArxivQueryResult
            ...
```

Worker 同时注册 Workflow 和 Activity：

```python
worker = Worker(
    client,
    task_queue=TASK_QUEUE,
    workflows=[ArxivSearchWorkflow],
    activities=[search_arxiv_batch],
)
```

以上代码用于说明边界，正式实现时以仓库当前安装的 `temporalio==1.31.0` 和 `mcp==2.0.0` API 为准。

## 6. 当前重试与超时处理

Activity 可能重复执行。例如 MCP 查询已经完成，但 Worker 在把结果上报给 Temporal 前退出，Temporal 可能再次执行该 Activity。

当前 arXiv 搜索是只读操作，重复查询不会产生写入副作用，因此适合由 Temporal 重试。

第一版暂定：

```python
start_to_close_timeout = timedelta(seconds=60)
schedule_to_close_timeout = timedelta(minutes=5)
```

- 单次 Activity 最多运行 60 秒；
- 包含排队、退避和重试在内，总时间最多 5 分钟；
- 网络错误、超时和 MCP 子进程意外退出允许重试；
- query 非法、工具不存在等永久错误不应重复重试。

这些时间是 spike 初始值，完成实际运行测试后再调整。

## 7. 当前已实现的内容

本阶段已经完成以下内容：

1. 在 `arxiv_models.py` 中定义 Activity 输入输出结构；
2. 在 `arxiv_activity.py` 中实现 `search_arxiv_batch`；
3. 在 `arxiv_workflow.py` 中调度该 Activity；
4. 在 `arxiv_worker.py` 中注册 Workflow 和 Activity；
5. 使用 `run_arxiv_activity.py` 独立验证 MCP 调用和结果转换；
6. 使用 `run_arxiv_workflow.py` 启动完整 Workflow；
7. 保留 `arxiv_server.py` 作为当前 stdio MCP Server。

这些实现暂时放在现有 spike 目录中，本阶段不建立正式生产目录结构。

## 8. 当前验证状态

已经验证：

1. Workflow 能收到 queries 并调用 Activity；
2. Activity 能通过 MCP 查询 arXiv；
3. 多个 query 仍在同一个 MCP session 内并发执行；
4. Activity 返回的数据可以被 Temporal 正常序列化；
5. Workflow 运行期间停止 Worker，重启 Worker 后 Workflow 从 `Running` 变为 `Completed`，最终输出正常；

本阶段以 Worker 中断并重启作为失败恢复验证，不再单独要求人为抛出 Activity 异常。

## 9. 暂不处理的内容

以下内容等实际需求出现后再设计和记录：

- MCP Streamable HTTP 部署；
- 通用 MCP Adapter 抽象；
- LLM、Writer、Verifier 等完整业务 Workflow；
- MCP 长任务和人工交互；
- 生产级认证、链路追踪和多 Worker 部署；
- Workflow Versioning 和复杂补偿流程。

## 10. 参考资料

- [Temporal：Activity Definition](https://docs.temporal.io/activity-definition)
- [Temporal Python SDK：错误处理与 Retry Policy](https://docs.temporal.io/develop/python/best-practices/error-handling)
- [Temporal Python：并行 Activity 示例](https://github.com/temporalio/samples-python/blob/main/hello/hello_parallel_activity.py)
- [MCP 官方文档](https://modelcontextprotocol.io/docs/)
