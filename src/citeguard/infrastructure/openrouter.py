"""Concrete OpenRouter structured-output boundary shared by CiteGuard Agents."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

OPENROUTER_CHAT_COMPLETIONS_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)
DEFAULT_OPENROUTER_MODEL = "deepseek/deepseek-v4-flash-0731"
ALLOWED_MODEL_PREFIXES = ("deepseek/", "qwen/", "z-ai/")
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_COMPLETION_TOKENS = 2_500

PromptMessages = Sequence[tuple[str, str]]
OutputModelT = TypeVar("OutputModelT", bound=BaseModel)


class OpenRouterError(RuntimeError):
    """Base error for CiteGuard model calls made through OpenRouter."""


class OpenRouterTransientError(OpenRouterError):
    """A provider or network failure that may succeed on retry."""


class OpenRouterPermanentError(OpenRouterError):
    """A request or response failure that should not be retried unchanged."""


@dataclass(frozen=True)
class OpenRouterSettings:
    """Credentials and model policy used by one OpenRouter request.

    Agent Activities create this boundary object from the process environment,
    while tests inject it directly. Construction guarantees a usable API key,
    an allowed model family, and a positive HTTP timeout.
    """

    api_key: str
    model: str = DEFAULT_OPENROUTER_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        """Validate credentials, model-family policy, and timeout bounds."""

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
        """Build validated settings from runtime-populated process variables.

        Returns:
            Credentials and the fixed or explicitly configured model selection.

        Raises:
            OpenRouterPermanentError: If neither supported API-key variable is
                present.
            ValueError: If an environment value violates model policy.

        Notes:
            This function does not load `.env`; the shell, IDE, or deployment
            runtime owns populating the process environment.
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
    max_completion_tokens: int = MAX_COMPLETION_TOKENS,
) -> OutputModelT:
    """Request and validate one strict JSON-Schema response from OpenRouter.

    Args:
        messages: Trusted policy and untrusted data messages from an Agent
            module.
        output_type: Pydantic model defining the only accepted response shape.
        settings: Optional explicit credentials and model settings for tests.
        client: Optional injected client for deterministic HTTP tests.
        max_completion_tokens: Output ceiling including any reasoning tokens.

    Returns:
        Model content validated as the requested Pydantic type.

    Raises:
        OpenRouterTransientError: If transport or provider conditions may
            recover.
        OpenRouterPermanentError: If the request or response is invalid
            unchanged.
        ValueError: If outgoing messages are malformed.

    Side effects:
        Sends one authenticated HTTPS request when no mock client is injected.

    Retry behavior:
        Retryable transport and provider failures are exposed as transient
        errors. Invalid requests and malformed responses are permanent.
    """

    if (
        not isinstance(max_completion_tokens, int)
        or isinstance(max_completion_tokens, bool)
        or max_completion_tokens <= 0
    ):
        raise ValueError("max_completion_tokens must be a positive integer")

    resolved = settings or OpenRouterSettings.from_environment()
    body = {
        "model": resolved.model,
        "messages": _convert_messages(messages),
        "temperature": 0,
        "max_tokens": max_completion_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": output_type.__name__.lower(),
                "strict": True,
                "schema": output_type.model_json_schema(),
            },
        },
        "provider": {"require_parameters": True},
    }
    headers = {
        "Authorization": f"Bearer {resolved.api_key}",
        "Content-Type": "application/json",
    }

    if client is not None:
        response = await _post(
            client,
            headers=headers,
            body=body,
            timeout_seconds=resolved.timeout_seconds,
        )
    else:
        async with httpx.AsyncClient() as owned_client:
            response = await _post(
                owned_client,
                headers=headers,
                body=body,
                timeout_seconds=resolved.timeout_seconds,
            )
    return _parse_response(response, output_type)


async def _post(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    body: dict[str, object],
    timeout_seconds: float,
) -> httpx.Response:
    """Send one provider request and classify HTTP failures by retryability.

    Args:
        client: Initialized client that owns connection behavior.
        headers: Authentication and content headers for OpenRouter.
        body: JSON-compatible structured chat-completion request.
        timeout_seconds: Maximum duration of this HTTP attempt.

    Returns:
        A successful response ready for provider-envelope validation.

    Raises:
        OpenRouterTransientError: If transport, timeout, rate limiting, or a
            provider server failure may recover on another attempt.
        OpenRouterPermanentError: If OpenRouter rejects the unchanged request.
    """

    try:
        response = await client.post(
            OPENROUTER_CHAT_COMPLETIONS_URL,
            headers=headers,
            json=body,
            timeout=timeout_seconds,
        )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise OpenRouterTransientError(
            "OpenRouter request failed before receiving a response"
        ) from exc

    if response.status_code in {408, 429} or response.status_code >= 500:
        raise OpenRouterTransientError(
            f"OpenRouter returned retryable HTTP {response.status_code}"
        )
    if response.is_error:
        raise OpenRouterPermanentError(
            f"OpenRouter returned HTTP {response.status_code}"
        )
    return response


def _parse_response(
    response: httpx.Response,
    output_type: type[OutputModelT],
) -> OutputModelT:
    """Validate the provider envelope and bound structured assistant content.

    Args:
        response: Successful provider response containing one assistant choice.
        output_type: Pydantic schema that defines the accepted JSON contract.

    Returns:
        Assistant content validated as the requested output model.

    Raises:
        OpenRouterPermanentError: If the envelope, content, JSON, or output
            schema is invalid. The finish reason is retained for empty-content
            diagnostics without exposing provider reasoning.
    """

    try:
        body = response.json()
        choice = body["choices"][0]
        content = choice["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise OpenRouterPermanentError(
            "OpenRouter response did not contain assistant content"
        ) from exc
    if not isinstance(content, str) or not content.strip():
        finish_reason = choice.get("finish_reason", "unknown")
        raise OpenRouterPermanentError(
            "OpenRouter response contained empty assistant content "
            f"(finish_reason={finish_reason})"
        )
    try:
        return output_type.model_validate_json(content)
    except ValidationError as exc:
        raise OpenRouterPermanentError(
            "OpenRouter response did not match the required schema"
        ) from exc


def _convert_messages(messages: PromptMessages) -> list[dict[str, str]]:
    """Convert role/content pairs into validated OpenRouter message objects."""

    supported_roles = {"system", "user", "assistant"}
    converted: list[dict[str, str]] = []
    for role, content in messages:
        if role not in supported_roles:
            raise ValueError(f"Unsupported OpenRouter message role: {role}")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("OpenRouter message content must not be blank")
        converted.append({"role": role, "content": content})
    if not converted:
        raise ValueError("OpenRouter messages must not be empty")
    return converted
