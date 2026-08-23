import json
import os
import unittest
from unittest.mock import patch

import httpx

from citeguard.planner.llm import (
    OpenRouterPermanentError,
    OpenRouterSettings,
    OpenRouterTransientError,
    request_structured_output,
)
from citeguard.planner.schemas import DecompositionOutput


class OpenRouterPlannerClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_requests_strict_schema_and_parses_output(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")
            self.assertEqual(body["response_format"]["type"], "json_schema")
            self.assertTrue(body["response_format"]["json_schema"]["strict"])
            self.assertTrue(body["provider"]["require_parameters"])

            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "items": [
                                            {"question": "What is an AI agent?"}
                                        ]
                                    }
                                )
                            }
                        }
                    ]
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            result = await request_structured_output(
                [("system", "Plan research."), ("user", "Define AI agents.")],
                DecompositionOutput,
                settings=OpenRouterSettings(
                    api_key="test-key",
                    model="deepseek/test-model",
                ),
                client=client,
            )

        self.assertEqual(result.items[0].question, "What is an AI agent?")

    async def test_rate_limit_is_transient(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(429, json={"error": "limited"})
        )

        async with httpx.AsyncClient(transport=transport) as client:
            with self.assertRaises(OpenRouterTransientError):
                await request_structured_output(
                    [("user", "Plan research.")],
                    DecompositionOutput,
                    settings=OpenRouterSettings(api_key="test-key"),
                    client=client,
                )

    async def test_invalid_structured_output_is_permanent(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": json.dumps({"items": []})}}
                    ]
                },
            )
        )

        async with httpx.AsyncClient(transport=transport) as client:
            with self.assertRaises(OpenRouterPermanentError):
                await request_structured_output(
                    [("user", "Plan research.")],
                    DecompositionOutput,
                    settings=OpenRouterSettings(api_key="test-key"),
                    client=client,
                )

    def test_environment_requires_an_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(OpenRouterPermanentError):
                OpenRouterSettings.from_environment()

    def test_disallowed_model_family_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "DeepSeek, Qwen, or Z.ai GLM"):
            OpenRouterSettings(
                api_key="test-key",
                model="openai/example-model",
            )


if __name__ == "__main__":
    unittest.main()
