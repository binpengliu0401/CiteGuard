"""Verify arXiv MCP response parsing and adapter input bounds."""

import json
import unittest

from mcp.types import CallToolResult, TextContent

from citeguard.researcher.arxiv import (
    ArxivMcpPermanentError,
    _parse_tool_result,
    _validate_search_input,
)


PAPER_PAYLOAD = [
    {
        "title": "Retrieval and factuality",
        "arxiv_id": "2401.00001",
        "summary": "A complete abstract.",
        "url": "https://arxiv.org/abs/2401.00001",
    }
]


class ArxivAdapterTests(unittest.TestCase):
    def test_parses_structured_tool_content(self) -> None:
        result = CallToolResult(
            content=[],
            structuredContent={"result": PAPER_PAYLOAD},
        )

        papers = _parse_tool_result(result)

        self.assertEqual(papers[0].source_id, "2401.00001")

    def test_parses_legacy_json_text_content(self) -> None:
        result = CallToolResult(
            content=[TextContent(type="text", text=json.dumps(PAPER_PAYLOAD))]
        )

        papers = _parse_tool_result(result)

        self.assertEqual(papers[0].summary, "A complete abstract.")

    def test_malformed_success_is_permanent(self) -> None:
        result = CallToolResult(content=[], structuredContent={"papers": []})

        with self.assertRaises(ArxivMcpPermanentError):
            _parse_tool_result(result)

    def test_query_bounds_are_validated_before_process_start(self) -> None:
        _validate_search_input(["one", "two"], 5)

        with self.assertRaises(ArxivMcpPermanentError):
            _validate_search_input(["query"] * 6, 5)
        with self.assertRaises(ArxivMcpPermanentError):
            _validate_search_input(["Query", " query "], 5)


if __name__ == "__main__":
    unittest.main()
