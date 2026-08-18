import asyncio

from arxiv_activity import search_arxiv_batch
from arxiv_models import ArxivSearchInput


async def main() -> None:
    search_input = ArxivSearchInput(
        queries=[
            "LLM reasoning",
            "RAG verification",
        ],
        max_results=2,
    )

    results = await search_arxiv_batch(search_input)

    for result in results:
        print(f"\n查询主题: {result.query}")

        for paper in result.papers:
            print(f"- {paper.title}")
            print(f"  arXiv ID: {paper.arxiv_id}")
            print(f"  URL: {paper.url}")


if __name__ == "__main__":
    asyncio.run(main())
