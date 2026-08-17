import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

server_path = Path(__file__).with_name("arxiv_server.py")
server_params = StdioServerParameters(
    command=sys.executable,
    args=[str(server_path)],
)


async def main():
    async with stdio_client(server_params) as (read, write):  # type: ignore # noqa: SIM117
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("可用工具:", [tool.name for tool in tools.tools])

            queries = ["LLM reasoning", "RAG verification", "durable agents"]
            results = await asyncio.gather(
                # 这里的 * 是“可迭代对象解包”，不是乘法。
                # numbers = [1, 2, 3]
                # print(numbers)    输出：[1, 2, 3]
                # print(*numbers)  相当于 print(1, 2, 3)，输出：1 2 3
                *(
                    session.call_tool(
                        "search_arxiv",
                        arguments={"query": query, "max_results": 3},
                    )
                    # 这是 Python 的生成器表达式语法
                    # numbers = (number * 2 for number in [1, 2, 3])
                    # 对 queries 中的每一个 query，创建一个 session.call_tool() 协程
                    for query in queries
                )
            )

            for query, result in zip(queries, results):
                print(f"\n搜索主题：{query}")
                for block in result.content:
                    if isinstance(block, TextContent):
                        print(block.text)


if __name__ == "__main__":
    asyncio.run(main())
