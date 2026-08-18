# CiteGuard 开发进展记录

> 用途：记录项目当前状态、关键设计决策和每次代码/重要文档更新，作为后续任务的首要阅读入口。
> 最后更新：2026-08-18

## 使用约定

后续处理项目任务时，按以下顺序获取上下文：

1. 首先阅读本文件，了解当前阶段、既有决策、相关文件和遗留事项。
2. 根据任务范围，只读取本文件指向的相关源码和设计文档。
3. 修改前检查相关源码及 `git status`、`git diff`，避免依赖过期摘要或覆盖已有改动。
4. 完成代码或重要设计变更后，在本文件顶部追加一条变更记录。
5. 本文件记录行为、接口、架构和验证结果，不复制普通实现细节。

本文件是项目导航和变更摘要；源码、测试结果及 Git 历史是最终事实来源。

## 当前项目状态

### 当前阶段

Temporal 与 MCP 集成的第一阶段 spike 已完成：arXiv MCP 调用已经封装为 Temporal Activity，最小端到端链路和 Worker 中断恢复均已验证。

### 已有能力

- 本地 Temporal Server 与基础 Workflow spike；
- MCP stdio client/server spike；
- 通过 MCP 工具查询 arXiv；
- Temporal × MCP 当前 spike 的 Activity 封装设计说明。
- Temporal Workflow 调度批量 arXiv MCP Activity 的端到端调用链。
- Workflow 运行期间 Worker 中断并重启后的恢复能力。

### 当前核心文件

| 文件 | 用途 |
| --- | --- |
| `test/temporal_test/hello_workflow.py` | 最小 Temporal Workflow 示例 |
| `test/temporal_test/hello_worker.py` | 最小 Temporal Worker 示例 |
| `test/temporal_test/run_hello.py` | Workflow 启动客户端 |
| `test/mcp_test/arxiv_client.py` | MCP stdio client 与并发查询 spike |
| `test/mcp_test/arxiv_server.py` | arXiv MCP Server spike |
| `test/temporal_test/arxiv_models.py` | Activity 输入输出数据结构 |
| `test/temporal_test/arxiv_activity.py` | 批量 arXiv MCP Activity |
| `test/temporal_test/arxiv_workflow.py` | 调度 arXiv Activity 的 Workflow |
| `test/temporal_test/arxiv_worker.py` | 注册 Workflow 和 Activity 的 Worker |
| `test/temporal_test/run_arxiv_activity.py` | 不经过 Temporal 的 Activity 调用验证 |
| `test/temporal_test/run_arxiv_workflow.py` | 完整 Workflow 启动客户端 |
| `file/temporal_mcp_framework.md` | Temporal × MCP 当前 spike 实现说明 |
| `file/process.md` | 当前状态与变更索引 |

### 已确定的架构约束

- Workflow 只负责确定性编排，不直接执行 MCP、HTTP、数据库、文件或子进程操作。
- 当前 MCP 调用全部放进 Activity，Workflow 不导入或使用 MCP Client。
- Workflow 与 Activity 之间传递稳定、可序列化的业务 DTO，不传递 MCP SDK 对象。
- Activity 按可能重复执行来设计；当前 arXiv 查询是只读操作，可以安全重试。
- 当前 stdio spike 优先采用“一批 queries 一个 Activity”，复用一次 MCP 子进程和连接。
- 当前只实现 Temporal、Activity 与 MCP stdio 的最小调用链，不提前实现通用 Adapter 和生产架构。

### 下一步

- 本阶段没有遗留验证项，等待下一项开发任务。

## 变更记录

记录按时间倒序排列，新记录添加在本节顶部。

---

### 2026-08-18 — 验证 Worker 中断恢复

#### 目标

确认 Workflow 运行期间 Worker 退出不会导致执行状态丢失。

#### 验证

- 启动 Workflow 后手动关闭 Worker。
- 重新启动 Worker 后，Workflow 状态从 `Running` 变为 `Completed`。
- Workflow 最终输出正常。

#### 当前状态

Worker 中断恢复已验证。

#### 后续事项

- 本阶段不再单独要求人为抛出 Activity 异常。

---

### 2026-08-18 — 完成 arXiv MCP Activity 最小调用链

#### 目标

把已有 arXiv MCP stdio 调用封装成 Temporal Activity，并通过 Workflow 完成端到端执行。

#### 设计决策

- 使用一个 `search_arxiv_batch` Activity 执行一批 queries，复用同一个 MCP 子进程和 session。
- Workflow 通过 Activity Type 字符串调度，避免导入包含 MCP 依赖的 Activity 模块。
- Workflow 和 Activity 之间使用 dataclass DTO，不传递 MCP SDK 对象。
- 单次 Activity 初始超时为 60 秒，包含重试的总预算为 5 分钟。

#### 修改内容

- 新增 arXiv 查询输入和结果数据结构。
- 新增批量 MCP 查询 Activity 及返回值解析。
- 新增调度 Activity 的 Workflow。
- 新增同时注册 Workflow 和 Activity 的 Worker。
- 新增 Activity 独立测试脚本和 Workflow 启动客户端。

#### 涉及文件

- `test/temporal_test/arxiv_models.py`
- `test/temporal_test/arxiv_activity.py`
- `test/temporal_test/arxiv_workflow.py`
- `test/temporal_test/arxiv_worker.py`
- `test/temporal_test/run_arxiv_activity.py`
- `test/temporal_test/run_arxiv_workflow.py`
- `file/temporal_mcp_framework.md`
- `file/process.md`

#### 验证

- 所有新增 Python 文件通过 `py_compile`。
- Activity 独立调用成功打印两个 arXiv 查询结果。
- Temporal Client → Workflow → Activity → MCP Server → arXiv 的完整调用成功打印两个查询结果。
- Workflow 运行期间关闭 Worker 并重新启动后，Workflow 恢复执行并正常完成。

#### 当前状态

基础调用链已完成。

#### 后续事项

- 本阶段任务已完成，等待下一项开发任务。

---

### 2026-08-18 — 收缩 Temporal × MCP 文档范围

#### 目标

让设计文档只描述当前正在进行的 MCP Activity 封装，避免尚未实现的长期架构造成信息干扰。

#### 设计决策

- 保留 Workflow 确定性边界、当前批量 Activity、输入输出、超时重试和验证目标。
- 移除远程 MCP、通用 Adapter、长任务、人工交互、生产安全和完整目录架构等未落地设计。
- 未实现内容只列入“暂不处理”，后续真正开发时再补充细节。

#### 修改内容

- 将项目级完整框架文档改为当前 spike 实现说明。
- 同步收缩本文件中的架构约束和下一步工作。

#### 涉及文件

- `file/temporal_mcp_framework.md`
- `file/process.md`

#### 验证

- 已检查 Markdown 结构和变更范围。

#### 当前状态

文档已与当前代码阶段对齐，Activity 代码尚未实现。

#### 后续事项

- 下一步实现 `search_arxiv_batch` Activity。

---

### 2026-08-18 — 建立开发进展记录

#### 目标

建立统一的项目状态和变更入口，减少后续任务重复扫描整个仓库产生的信息干扰。

#### 设计决策

- `process.md` 作为导航和摘要，不替代源码、测试及 Git 历史。
- 后续优先读取本文件，再根据文件索引按需读取源码。
- 每次代码或重要设计更新完成后同步更新本文件。
- 只记录影响行为、接口、架构和后续工作的内容。

#### 修改内容

- 新增当前项目状态、核心文件索引、架构约束和下一步工作。
- 建立固定的变更记录格式和维护约定。

#### 涉及文件

- `file/process.md`

#### 验证

- Markdown 文件已创建。

#### 当前状态

已完成。

#### 后续事项

- 后续每次完成代码或重要设计变更时持续维护。

---

### 2026-08-18 — 建立 Temporal × MCP 小框架设计基线

#### 目标

明确 Temporal Workflow/Activity 的确定性边界，并定义 CiteGuard 中 MCP 调用的统一接入方式。

#### 设计决策

- Workflow 负责确定性编排，Activity 封装外部调用和副作用。
- 当前 MCP stdio 阶段采用批量查询 Activity，避免每条 query 重复启动 MCP 子进程。
- 长驻 Streamable HTTP 阶段默认采用单工具调用 Activity，以获得独立重试和观测能力。
- MCP 协议与 SDK 兼容细节封装在 Adapter 中，不进入 Workflow。
- 设计基线参考 MCP `2026-07-28` 正式规范，同时兼容当前 spike 的 SDK 调用方式。

#### 修改内容

- 新增 Temporal 确定性、replay 和版本演进约束。
- 新增 Activity 粒度、幂等、超时、重试和 heartbeat 规范。
- 新增 stdio 与 Streamable HTTP 的分阶段集成方案。
- 新增 DTO、MCP Adapter、目录结构、安全、可观测性和测试规范。
- 给出 arXiv Workflow/Activity 结构伪代码。

#### 涉及文件

- `file/temporal_mcp_framework.md`

#### 验证

- 已执行 `git diff --check`，未发现格式问题。

#### 当前状态

设计文档已完成，尚未开始 Activity 实现。

#### 后续事项

- 按设计基线实现 arXiv MCP Activity 和 Research Workflow。

## 变更记录模板

```markdown
## YYYY-MM-DD — 变更标题

### 目标

本次要解决的问题。

### 设计决策

采用的方案、边界和主要取舍。

### 修改内容

- 新增或修改的行为。

### 涉及文件

- `path/to/file`

### 验证

- 执行的检查、测试及结果。

### 当前状态

已完成到什么程度。

### 后续事项

- 尚未实现或需要继续验证的事项。
```
