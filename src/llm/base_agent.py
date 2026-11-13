"""Base LLM agent for coding-* services.

Wraps pydantic-ai + an OpenAI-compatible endpoint (inference-router in
production). Subclasses set ``schema_id``, ``response_model``, and provide
a ``system_prompt`` (or override ``get_system_prompt``); they then call
``self._call_llm(prompt)`` to get a parsed response model.

The shared ``httpx.AsyncClient`` carries event hooks that:
1. Inject X-Tenant-Id / X-Job-Id / X-License-Id / X-Schema-Id headers from
   ``llm_request_context()``.
2. Capture X-Inference-Id / X-Failover-Chain-Id from the response into a
   contextvar sink that ``_call_llm`` reads back after the run completes.

This module is import-safe: pydantic-ai / openai are imported lazily so
just importing the package doesn't pull heavy deps into every consumer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextvars import ContextVar
from typing import Any, ClassVar

import httpx
from coding_client.exceptions.pydantic_ai_exceptions import LLMEmptyResponseError
from coding_client.llm.context import (
    apply_request_headers,
    capture_response_metadata,
    install_response_sink,
    reset_response_sink,
)
from coding_client.llm.settings import LLMSettings, get_llm_settings
from pydantic import BaseModel

# Module-level singleton, mirrors karma's pattern.
_llm_http_client: httpx.AsyncClient | None = None
_last_metadata: ContextVar[dict[str, str]] = ContextVar(
    "coding_client_last_llm_metadata",
    default={},
)


def _get_llm_http_client(settings: LLMSettings) -> httpx.AsyncClient:
    """Get or create the shared httpx client used for all LLM-plane calls."""
    global _llm_http_client
    if _llm_http_client is None or _llm_http_client.is_closed:
        _llm_http_client = httpx.AsyncClient(
            timeout=settings.llm_api_timeout_seconds,
            event_hooks={
                "request": [apply_request_headers],
                "response": [capture_response_metadata],
            },
        )
    return _llm_http_client


async def close_llm_clients() -> None:
    """Close the shared httpx client. Call from FastAPI lifespan shutdown."""
    global _llm_http_client
    if _llm_http_client is not None and not _llm_http_client.is_closed:
        await _llm_http_client.aclose()
    _llm_http_client = None


def last_inference_id() -> str | None:
    """Return X-Inference-Id captured during the most recent _call_llm, if any."""
    return _last_metadata.get({}).get("inference_id")


def last_failover_chain_id() -> str | None:
    """Return X-Failover-Chain-Id captured during the most recent _call_llm, if any."""
    return _last_metadata.get({}).get("failover_chain_id")


class BaseLLMAgent(ABC):
    """Abstract base class for coding-* LLM agents.

    Subclasses set:

    * ``schema_id``: stable identifier registered in model-registry.
    * ``response_model``: pydantic model for structured output.
    * ``system_prompt``: default system prompt (overridable per call).
    """

    schema_id: ClassVar[str] = ""
    response_model: ClassVar[type[BaseModel] | None] = None
    system_prompt: ClassVar[str] = ""

    def __init__(self, settings: LLMSettings | None = None):
        """Initialize the agent.

        Args:
            settings: Optional LLMSettings override; defaults to the singleton.
        """
        self.settings = settings or get_llm_settings()
        if not self.schema_id:
            raise ValueError(f"{type(self).__name__} must set the class attribute 'schema_id'")

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Execute the agent's main task. Subclasses implement."""
        raise NotImplementedError

    def get_system_prompt(self) -> str:
        """Return the system prompt for this call (overridable)."""
        return self.system_prompt

    async def _call_llm(
        self,
        prompt: str,
        system_prompt: str | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> Any:
        """Call the configured LLM plane via pydantic-ai.

        Args:
            prompt: User prompt to send.
            system_prompt: Optional override; defaults to ``get_system_prompt()``.
            response_model: Optional structured-output type; defaults to the
                class-level ``response_model``.

        Returns:
            Parsed pydantic instance when a response model is in play,
            otherwise the raw stripped response text.

        Raises:
            LLMEmptyResponseError: Underlying pydantic-ai retry budget
                exhausted, or empty/whitespace text in unstructured mode.
            httpx.HTTPError: Transport-level failure.
        """
        # Lazy imports — keep coding-client importable without pydantic-ai.
        from openai import AsyncOpenAI
        from pydantic_ai import Agent
        from pydantic_ai.exceptions import AgentRunError
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        if system_prompt is None:
            system_prompt = self.get_system_prompt()
        if response_model is None:
            response_model = self.response_model

        http_client = _get_llm_http_client(self.settings)

        # Mutable sink — see context.py for the rationale.
        sink: dict[str, str] = {}
        sink_token = install_response_sink(sink)

        openai_client = AsyncOpenAI(
            base_url=self.settings.llm_api_base_url or None,
            api_key=self.settings.llm_api_key or "unused",
            http_client=http_client,
            max_retries=0,
        )
        provider = OpenAIProvider(openai_client=openai_client)
        model = OpenAIChatModel(self.schema_id, provider=provider)

        output_type: Any = response_model if response_model is not None else str
        pai_agent = Agent(
            model,
            system_prompt=system_prompt,
            output_type=output_type,
            retries=1,
        )

        try:
            result = await pai_agent.run(prompt)
        except AgentRunError as exc:
            _last_metadata.set(dict(sink))
            raise LLMEmptyResponseError(
                f"LLM plane returned no usable output for {type(self).__name__}: {exc}",
                agent_name=type(self).__name__,
                cause=exc,
            ) from exc
        finally:
            reset_response_sink(sink_token)

        _last_metadata.set(dict(sink))

        if response_model is not None:
            return result.output

        output = result.output
        if output is None:
            raise LLMEmptyResponseError(
                f"LLM plane returned empty output for {type(self).__name__}",
                agent_name=type(self).__name__,
            )
        text = str(output).strip()
        if not text:
            raise LLMEmptyResponseError(
                f"LLM plane returned whitespace-only output for {type(self).__name__}",
                agent_name=type(self).__name__,
            )
        return text
