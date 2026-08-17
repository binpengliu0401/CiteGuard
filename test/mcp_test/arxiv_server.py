import feedparser
import httpx
from mcp.server import MCPServer

mcp = MCPServer("arxiv-server")
ARXIV_API = "https://export.arxiv.org/api/query"


@mcp.tool()
async def search_arxiv(query: str, max_results: int = 5) -> list[dict]:
    """按关键词搜索arXiv论文，返回标题/arxiv_id/摘要/链接"""
    params = {"search_query": f"all:{query}", "start": 0, "max_results": max_results}
    # 建立异步HTTP客户端，async with会在代码块结束后自动关闭连接和释放资源
    # search_arxiv A：发送请求 -> 暂停等待 --------> 收到结果 -> 继续
    # 事件循环：                        执行任务 B、C
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 发送请求并等待响应。等待期间不会阻塞整个事件循环
        resp = await client.get(ARXIV_API, params=params)
        # 检查已经收到的响应
        # 2xx：继续执行
        # 4xx 或 5xx：抛出 HTTPStatusError
        resp.raise_for_status()

    feed = feedparser.parse(resp.text)
    return [
        {
            "title": e.title.strip().replace("\n", " "),
            "arxiv_id": e.id.split("/abs/")[-1],
            "summary": e.summary.strip().replace("\n", " ")[:300],
            "url": e.id,
        }
        for e in feed.entries
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")
