"""Tests for coding_client.llm.base_agent."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from coding_client.exceptions.pydantic_ai_exceptions import LLMEmptyResponseError
from coding_client.llm import base_agent as base_agent_mod
from coding_client.llm.base_agent import (
    BaseLLMAgent,
    last_failover_chain_id,
    last_inference_id,
)
from coding_client.llm.responses import TestFailureAnalysisResponse
from coding_client.llm.settings import LLMSettings


class _DummyAgent(BaseLLMAgent):
    schema_id = "test_failure_analysis"
    response_model = TestFailureAnalysisResponse
    system_prompt = "diagnose"

    async def execute(self, **kwargs: Any) -> Any:  # pragma: no cover
        return await self._call_llm("prompt")


@pytest.fixture
def settings() -> LLMSettings:
    return LLMSettings(
        llm_api_base_url="http://router/v1",
        llm_api_key="x",
        llm_mode="inference_router",
        llm_api_timeout_seconds=10.0,
    )


def test_subclass_must_set_schema_id(settings):
    class Bad(BaseLLMAgent):
        async def execute(self, **kwargs: Any) -> Any:  # pragma: no cover
            return None

    with pytest.raises(ValueError, match="schema_id"):
        Bad(settings=settings)


@pytest.mark.asyncio
async def test_call_llm_returns_parsed_model_and_captures_metadata(settings):
    agent = _DummyAgent(settings=settings)

    fake_output = TestFailureAnalysisResponse(
        root_cause="x",
        suggested_fix="y",
        confidence=0.9,
        category="assertion",
    )
    fake_result = MagicMock()
    fake_result.output = fake_output

    fake_pai_agent = MagicMock()
    fake_pai_agent.run = AsyncMock(return_value=fake_result)

    def _populate_sink_then_return(*_a, **_k):
        # Mimic what the response event hook does inside a real run.
        sink = base_agent_mod._last_metadata.get({})
        # In the real flow the sink lives in context.py's contextvar; here
        # we simulate by setting last metadata directly via the helper.
        del sink  # unused
        return fake_pai_agent

    with (
        patch("openai.AsyncOpenAI") as mock_openai,
        patch("pydantic_ai.providers.openai.OpenAIProvider") as mock_provider,
        patch("pydantic_ai.models.openai.OpenAIChatModel") as mock_model,
        patch("pydantic_ai.Agent", side_effect=_populate_sink_then_return) as mock_agent_cls,
    ):
        mock_openai.return_value = MagicMock()
        mock_provider.return_value = MagicMock()
        mock_model.return_value = MagicMock()

        # Manually populate the metadata sink before run, then verify
        # _call_llm copies it into the last-metadata contextvar.
        async def _run_simulating_hook(prompt: str):
            from coding_client.llm import context as ctx_mod

            sink = ctx_mod._llm_response_metadata.get()
            if sink is not None:
                sink["inference_id"] = "inf-1"
                sink["failover_chain_id"] = "chain-1"
            return fake_result

        fake_pai_agent.run = _run_simulating_hook

        result = await agent._call_llm("hello world")

    assert result is fake_output
    assert last_inference_id() == "inf-1"
    assert last_failover_chain_id() == "chain-1"
    mock_openai.assert_called_once()
    _, kwargs = mock_openai.call_args
    assert kwargs["max_retries"] == 0
    assert kwargs["api_key"] == "x"
    mock_agent_cls.assert_called_once()


@pytest.mark.asyncio
async def test_agent_run_error_translates_to_llm_empty_response(settings):
    from pydantic_ai.exceptions import AgentRunError

    agent = _DummyAgent(settings=settings)

    fake_pai_agent = MagicMock()
    fake_pai_agent.run = AsyncMock(side_effect=AgentRunError("model gave up"))

    with (
        patch("openai.AsyncOpenAI"),
        patch("pydantic_ai.providers.openai.OpenAIProvider"),
        patch("pydantic_ai.models.openai.OpenAIChatModel"),
        patch("pydantic_ai.Agent", return_value=fake_pai_agent),
        pytest.raises(LLMEmptyResponseError) as excinfo,
    ):
        await agent._call_llm("hello")

    assert excinfo.value.agent_name == "_DummyAgent"
    assert isinstance(excinfo.value.cause, AgentRunError)


@pytest.mark.asyncio
async def test_empty_text_in_unstructured_mode_raises(settings):
    class _UnstructuredAgent(BaseLLMAgent):
        schema_id = "x"
        response_model = None
        system_prompt = "p"

        async def execute(self, **kwargs: Any) -> Any:  # pragma: no cover
            return None

    agent = _UnstructuredAgent(settings=settings)
    fake_pai_agent = MagicMock()
    fake_result = MagicMock()
    fake_result.output = "   "
    fake_pai_agent.run = AsyncMock(return_value=fake_result)

    with (
        patch("openai.AsyncOpenAI"),
        patch("pydantic_ai.providers.openai.OpenAIProvider"),
        patch("pydantic_ai.models.openai.OpenAIChatModel"),
        patch("pydantic_ai.Agent", return_value=fake_pai_agent),
        pytest.raises(LLMEmptyResponseError),
    ):
        await agent._call_llm("p")
