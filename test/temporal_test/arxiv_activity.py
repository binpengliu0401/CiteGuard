import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from arxiv_models import ArxivPaper, ArxivQueryResult, ArxivSearchInput
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent
from temporalio import activity
from temporalio.exceptions import ApplicationError

SERVER_PATH = Path(__file__).resolve().parents[1] / "mcp_test" / "arxiv_server.py"


@activity.defn(name="search_arxiv_batch")
async def search_arxiv_batch(
    input: ArxivSearchInput,
) -> list[ArxivQueryResult]:
    """通过一个MCP session 并发执行多条arXiv查询。"""
    queries = [query.strip() for query in input.queries if query.strip()]

    if not queries:
        raise ApplicationError(
            "queries 不能为空",
            type="InvalidArxivSearchInput",
            non_retryable=True,
        )

    if input.max_results <= 0:
        raise ApplicationError(
            "max_results 必须大于 0",
            type="InvalidArxivSearchInput",
            non_retryable=True,
        )

    server_params = StdioServerParameters(
        command=sys.executable, args=[str(SERVER_PATH)]
    )

    async with stdio_client(server_params) as (read, write):  # noqa: SIM117
        async with ClientSession(read, write) as session:
            await session.initialize()

            results = await asyncio.gather(
                *(
                    session.call_tool(
                        "search_arxiv",
                        arguments={
                            "query": query,
                            "max_results": input.max_results,
                        },
                    )
                    for query in queries
                )
            )
    return [
        ArxivQueryResult(
            query=query,
            papers=_parse_papers(result),
        )
        for query, result in zip(queries, results)
    ]


def _parse_papers(result: CallToolResult) -> list[ArxivPaper]:
    """把MCP SDK 返回值转换为项目自己的数据结构"""

    if result.is_error:
        raise RuntimeError("MCP search_arxiv 调用失败")

    raw_papers = _get_result_data(result)

    if not isinstance(raw_papers, list):
        raise ApplicationError(
            "search_arxiv 返回值不是论文列表",
            type="InvalidMcpResult",
            non_retryable=True,
        )

    try:
        return [
            ArxivPaper(
                title=paper["title"],
                arxiv_id=paper["arxiv_id"],
                summary=paper["summary"],
                url=paper["url"],
            )
            for paper in raw_papers
        ]
    except (KeyError, TypeError) as exc:
        raise ApplicationError(
            "search_arxiv 返回的论文结构不正确",
            type="InvalidMcpResult",
            non_retryable=True,
        ) from exc


def _get_result_data(result: CallToolResult) -> Any:
    """兼容 MCP 的 structuredContent 和文本 JSON 返回形式。"""

    if result.structured_content is not None:
        data = result.structured_content

        if isinstance(data, dict) and "result" in data:
            return data["result"]

        return data

    text_blocks = [
        block.text for block in result.content if isinstance(block, TextContent)
    ]

    if len(text_blocks) != 1:
        raise ApplicationError(
            "search_arxiv没有返回唯一的文本结果",
            type="InvalidMcpResult",
            non_retryable=True,
        )

    try:
        return json.loads(text_blocks[0])
    except json.JSONDecodeError as exc:
        raise ApplicationError(
            "search_arxiv 返回的内容不是合法 JSON",
            type="InvalidMcpResult",
            non_retryable=True,
        ) from exc
