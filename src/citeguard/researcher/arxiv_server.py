"""Expose the formal arXiv search Tool over MCP stdio."""

import feedparser
import httpx
from mcp.server import MCPServer

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_TIMEOUT_SECONDS = 30.0
MAX_RESULTS_PER_QUERY = 5
ARXIV_USER_AGENT = "CiteGuard/0.1 (academic research client)"

mcp = MCPServer("citeguard-arxiv")


@mcp.tool()
async def search_arxiv(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search arXiv for candidate papers matching a keyword query.

    Use this tool when a research task requires candidate academic papers from
    arXiv. Search results are not proof that a paper supports a claim.

    Args:
        query: Keyword expression sent to the arXiv full-record search.
        max_results: Maximum number of candidate papers to return, from 1 to 5.

    Returns:
        Papers containing title, arXiv ID, full abstract summary, and URL.

    Constraints:
        The Researcher must still evaluate relevance and evidence quality.
    """

    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must not be blank")
    if not isinstance(max_results, int) or isinstance(max_results, bool):
        raise TypeError("max_results must be an integer")
    if not 1 <= max_results <= MAX_RESULTS_PER_QUERY:
        raise ValueError("max_results must be between 1 and 5")

    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
    }
    # arXiv asks API clients to identify themselves so rate limiting and abuse
    # handling do not treat the request as anonymous browser traffic.
    async with httpx.AsyncClient(
        timeout=ARXIV_TIMEOUT_SECONDS,
        headers={"User-Agent": ARXIV_USER_AGENT},
    ) as client:
        response = await client.get(ARXIV_API_URL, params=params)
        response.raise_for_status()

    feed = feedparser.parse(response.text)
    if getattr(feed, "bozo", False) and not feed.entries:
        raise ValueError("arXiv returned a malformed feed")

    return [
        {
            "title": _normalize_text(entry.title),
            "arxiv_id": entry.id.split("/abs/")[-1],
            "summary": _normalize_text(entry.summary),
            "url": entry.id,
        }
        for entry in feed.entries
    ]


def _normalize_text(value: str) -> str:
    """Collapse feed formatting whitespace while preserving full content."""

    return " ".join(value.split())


if __name__ == "__main__":
    mcp.run(transport="stdio")
