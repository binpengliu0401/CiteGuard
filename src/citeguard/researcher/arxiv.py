"""Project-owned adapter for concurrent arXiv calls over one MCP session."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent

MAX_SEARCH_QUERIES = 5
MAX_RESULTS_PER_QUERY = 5
MAX_UNIQUE_CANDIDATES = 12


class ArxivMcpError(RuntimeError):
    """Base error for the Researcher's local arXiv MCP boundary."""


class ArxivMcpTransientError(ArxivMcpError):
    """A subprocess, transport, or Tool failure eligible for retry."""


class ArxivMcpPermanentError(ArxivMcpError):
    """A deterministic input or protocol failure not repaired by retry."""


@dataclass(frozen=True)
class ArxivPaper:
    """One complete candidate paper returned across the MCP trust boundary.

    The adapter constructs this project-owned value from Tool output. Prompt
    builders consume it only after title, identity, abstract, and URL have all
    passed nonblank validation.
    """

    title: str
    source_id: str
    summary: str
    url: str

    def __post_init__(self) -> None:
        """Require complete candidate metadata before model evaluation."""

        for field_name in ("title", "source_id", "summary", "url"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"ArxivPaper.{field_name} must not be blank")


async def search_arxiv_candidates(
    queries: list[str],
    *,
    max_results_per_query: int = MAX_RESULTS_PER_QUERY,
) -> list[ArxivPaper]:
    """Search several queries concurrently through one initialized MCP session.

    Args:
        queries: One to five validated, materially distinct search expressions.
        max_results_per_query: Candidate limit for each Tool call, from 1 to 5.

    Returns:
        Deduplicated papers in query/result order, capped at twelve candidates.

    Raises:
        ArxivMcpPermanentError: If input or successful Tool output is malformed.
        ArxivMcpTransientError: If the subprocess, transport, or Tool call fails.

    Side effects:
        Starts the local MCP server and performs arXiv network requests.
    """

    _validate_search_input(queries, max_results_per_query)
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "citeguard.researcher.arxiv_server"],
    )

    try:
        async with stdio_client(server) as (read, write):  # type: ignore[arg-type]
            async with ClientSession(read, write) as session:
                await session.initialize()
                results = await asyncio.gather(
                    *(
                        session.call_tool(
                            "search_arxiv",
                            arguments={
                                "query": query,
                                "max_results": max_results_per_query,
                            },
                        )
                        for query in queries
                    )
                )
    except ArxivMcpError:
        raise
    except Exception as exc:
        raise ArxivMcpTransientError(
            "arXiv MCP session or Tool call failed"
        ) from exc

    papers: list[ArxivPaper] = []
    seen_ids: set[str] = set()
    for result in results:
        for paper in _parse_tool_result(result):
            if paper.source_id in seen_ids:
                continue
            seen_ids.add(paper.source_id)
            papers.append(paper)
            if len(papers) == MAX_UNIQUE_CANDIDATES:
                return papers
    return papers


def _validate_search_input(queries: list[str], max_results_per_query: int) -> None:
    """Validate bounds before starting an external process."""

    if not isinstance(queries, list) or not 1 <= len(queries) <= MAX_SEARCH_QUERIES:
        raise ArxivMcpPermanentError("queries must contain between 1 and 5 items")
    keys: set[str] = set()
    for query in queries:
        if not isinstance(query, str) or not query.strip():
            raise ArxivMcpPermanentError("queries must not contain blank items")
        key = " ".join(query.split()).casefold()
        if key in keys:
            raise ArxivMcpPermanentError("queries must be distinct")
        keys.add(key)
    if (
        not isinstance(max_results_per_query, int)
        or isinstance(max_results_per_query, bool)
        or not 1 <= max_results_per_query <= MAX_RESULTS_PER_QUERY
    ):
        raise ArxivMcpPermanentError(
            "max_results_per_query must be an integer between 1 and 5"
        )


def _parse_tool_result(result: Any) -> list[ArxivPaper]:
    """Convert one successful MCP response into project-owned paper objects.

    Args:
        result: Untrusted response returned by one MCP Tool invocation.

    Returns:
        Candidate papers that satisfy the local transport contract.

    Raises:
        ArxivMcpTransientError: If the Tool reports an execution failure.
        ArxivMcpPermanentError: If a successful response uses an unsupported
            result type or contains malformed JSON or paper fields.
    """

    if not isinstance(result, CallToolResult):
        raise ArxivMcpPermanentError("arXiv Tool returned an unsupported result type")
    if result.is_error:
        raise ArxivMcpTransientError("arXiv Tool reported an execution error")

    payload: Any
    if result.structured_content is not None:
        payload = result.structured_content
        if isinstance(payload, dict) and set(payload) == {"result"}:
            payload = payload["result"]
    else:
        text_blocks = [
            block.text for block in result.content if isinstance(block, TextContent)
        ]
        if len(text_blocks) != 1:
            raise ArxivMcpPermanentError(
                "arXiv Tool response must contain one JSON text block"
            )
        try:
            payload = json.loads(text_blocks[0])
        except (TypeError, ValueError) as exc:
            raise ArxivMcpPermanentError(
                "arXiv Tool text response was not valid JSON"
            ) from exc

    if not isinstance(payload, list):
        raise ArxivMcpPermanentError("arXiv Tool payload must be a paper list")

    papers: list[ArxivPaper] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ArxivMcpPermanentError("arXiv Tool paper must be an object")
        try:
            papers.append(
                ArxivPaper(
                    title=item["title"],
                    source_id=item["arxiv_id"],
                    summary=item["summary"],
                    url=item["url"],
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ArxivMcpPermanentError(
                "arXiv Tool paper did not match the required contract"
            ) from exc
    return papers
