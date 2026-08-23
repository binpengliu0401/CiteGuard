"""OpenRouter structured-output boundary for Planner model calls."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from citeguard.planner.prompts import PromptMessages

OPENROUTER_CHAT_COMPLETIONS_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)
# Keep a fixed model slug so a provider alias cannot change behavior unnoticed.
DEFAULT_OPENROUTER_MODEL = "deepseek/deepseek-v4-flash-0731"
# Product policy intentionally excludes OpenAI, Anthropic, Google, and xAI.
ALLOWED_MODEL_PREFIXES = ("deepseek/", "qwen/", "z-ai/")
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_COMPLETION_TOKENS = 2_000

OutputModelT = TypeVar("OutputModelT", bound=BaseModel)


class OpenRouterError(RuntimeError):
    """Base error for Planner calls made through OpenRouter."""


class OpenRouterTransientError(OpenRouterError):
    """A provider or network failure that may succeed on retry."""


class OpenRouterPermanentError(OpenRouterError):
    """A request or response failure that should not be retried unchanged."""


@dataclass(frozen=True)
class OpenRouterSettings:
    """Validated settings required for one OpenRouter request.

    The object is immutable so request code cannot accidentally replace the key,
    model, or timeout after validation.
    """

    api_key: str
    model: str = DEFAULT_OPENROUTER_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        """Validate credentials, product model policy, and timeout bounds."""

        if not self.api_key.strip():
            raise ValueError("OpenRouter API key must not be blank")
        if not self.model.strip():
            raise ValueError("OpenRouter model must not be blank")
        if not self.model.startswith(ALLOWED_MODEL_PREFIXES):
            raise ValueError(
                "OpenRouter model must be from DeepSeek, Qwen, or Z.ai GLM"
            )
        if self.timeout_seconds <= 0:
            raise ValueError("OpenRouter timeout must be greater than zero")

    @classmethod
    def from_environment(cls) -> OpenRouterSettings:
        """Build settings from process variables, not directly from `.env`.

        A shell, IDE, container, or dotenv loader must populate the process
        environment before this method runs. OPENROUTER_API_KEY is preferred;
        API_KEY remains accepted because it is the project's current local name.

        Returns:
            Validated credentials, model selection, and request timeout.

        Raises:
            OpenRouterPermanentError: If neither supported API-key variable is
                present.
            ValueError: If an environment value violates model or timeout policy.
        """

        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("API_KEY")

        if api_key is None:
            raise OpenRouterPermanentError(
                "OPENROUTER_API_KEY or API_KEY is required"
            )

        return cls(
            api_key=api_key,
            model=os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
        )


async def request_structured_output(
    messages: PromptMessages,
    output_type: type[OutputModelT],
    *,
    settings: OpenRouterSettings | None = None,
    client: httpx.AsyncClient | None = None,
) -> OutputModelT:
    """Request and validate one strict JSON-Schema response from OpenRouter.

    Args:
        messages: Role/content pairs produced by the Planner prompt layer.
        output_type: Pydantic model defining the only accepted response shape.
        settings: Optional explicit configuration, primarily useful in tests.
        client: Optional injected HTTP client for deterministic mock transports.

    Returns:
        A validated instance of `output_type`, never an untyped provider dict.

    Raises:
        OpenRouterTransientError: For network or retryable provider failures.
        OpenRouterPermanentError: For nonretryable HTTP or response failures.
        ValueError: If the outgoing messages are invalid.
    """

    resolved_settings = settings or OpenRouterSettings.from_environment()
    request_body = {
        "model": resolved_settings.model,
        "messages": _to_openrouter_messages(messages),
        # Planner output should be stable enough for deterministic downstream
        # assembly; creativity is not useful at this boundary.
        "temperature": 0,
        "max_tokens": MAX_COMPLETION_TOKENS,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": output_type.__name__.lower(),
                # Strict mode rejects provider fields not declared by Pydantic.
                "strict": True,
                "schema": output_type.model_json_schema(),
            },
        },
        "provider": {
            # OpenRouter must route only to endpoints that support every requested
            # structured-output parameter instead of silently dropping one.
            "require_parameters": True,
        },
    }
    headers = {
        "Authorization": f"Bearer {resolved_settings.api_key}",
        "Content-Type": "application/json",
    }

    # Tests inject a MockTransport-backed client. Production owns a short-lived
    # client here until a Worker-level client lifecycle is introduced.
    if client is not None:
        response = await _post(
            client,
            headers=headers,
            request_body=request_body,
            timeout_seconds=resolved_settings.timeout_seconds,
        )
    else:
        async with httpx.AsyncClient() as owned_client:
            response = await _post(
                owned_client,
                headers=headers,
                request_body=request_body,
                timeout_seconds=resolved_settings.timeout_seconds,
            )

    return _parse_response(response, output_type)


async def _post(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    request_body: dict[str, object],
    timeout_seconds: float,
) -> httpx.Response:
    """Send one provider request and classify failures by retryability.

    Args:
        client: Initialized asynchronous HTTP client used for the request.
        headers: Authentication and content headers for OpenRouter.
        request_body: JSON-compatible chat-completion payload.
        timeout_seconds: Maximum duration of this HTTP attempt.

    Returns:
        A successful OpenRouter HTTP response ready for content validation.

    Raises:
        OpenRouterTransientError: If transport, timeout, rate-limit, or server
            failure may succeed on a later attempt.
        OpenRouterPermanentError: If the request is rejected for a reason that
            requires changed credentials, model configuration, or input.
    """

    try:
        response = await client.post(
            OPENROUTER_CHAT_COMPLETIONS_URL,
            headers=headers,
            json=request_body,
            timeout=timeout_seconds,
        )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise OpenRouterTransientError(
            "OpenRouter request failed before receiving a response"
        ) from exc

    # Timeouts, rate limits, and server failures may succeed on a later attempt.
    if response.status_code in {408, 429} or response.status_code >= 500:
        raise OpenRouterTransientError(
            f"OpenRouter returned retryable HTTP {response.status_code}"
        )

    # Other 4xx responses generally require changed credentials, model, or input.
    if response.is_error:
        raise OpenRouterPermanentError(
            f"OpenRouter returned HTTP {response.status_code}"
        )

    return response


def _parse_response(
    response: httpx.Response,
    output_type: type[OutputModelT],
) -> OutputModelT:
    """Validate provider content before it crosses into Planner code.

    Args:
        response: Successful provider response containing assistant content.
        output_type: Pydantic model defining the accepted JSON contract.

    Returns:
        Structured assistant content validated as `output_type`.

    Raises:
        OpenRouterPermanentError: If the response envelope, assistant content,
            JSON, or schema validation is invalid.
    """

    try:
        response_body = response.json()
        content = response_body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise OpenRouterPermanentError(
            "OpenRouter response did not contain assistant content"
        ) from exc

    if not isinstance(content, str) or not content.strip():
        raise OpenRouterPermanentError(
            "OpenRouter response contained empty assistant content"
        )

    # Validation is the trust boundary: only typed data can leave llm.py.
    try:
        return output_type.model_validate_json(content)
    except ValidationError as exc:
        raise OpenRouterPermanentError(
            "OpenRouter response did not match the required schema"
        ) from exc


def _to_openrouter_messages(
    messages: PromptMessages,
) -> list[dict[str, str]]:
    """Convert validated Planner messages into OpenRouter wire objects.

    Args:
        messages: Internal role/content pairs produced by the prompt layer.

    Returns:
        Messages using OpenRouter's `role` and `content` object shape.

    Raises:
        ValueError: If no messages are supplied or a role or content is invalid.
    """

    supported_roles = {"system", "user", "assistant"}
    converted: list[dict[str, str]] = []

    for role, content in messages:
        if role not in supported_roles:
            raise ValueError(f"Unsupported OpenRouter message role: {role}")
        if not content.strip():
            raise ValueError("OpenRouter message content must not be blank")

        converted.append({"role": role, "content": content})

    if not converted:
        raise ValueError("OpenRouter messages must not be empty")

    return converted
