"""Shared LLM client for coding-* services.

Public API:
    BaseLLMAgent: Abstract base class wrapping pydantic-ai + inference-router.
    LLMSettings: pydantic-settings model for env vars.
    llm_request_context: contextmanager attaching X-Tenant-Id / X-Job-Id /
        X-License-Id / X-Schema-Id headers to LLM-plane HTTP requests.
    last_inference_id / last_failover_chain_id: helpers to read the
        inference-router metadata captured from the most recent _call_llm.
    AgentRouting + AGENT_ROUTING_REGISTRY: routing-rule registry used by
        scripts/register_routing_rules.py to bootstrap model-registry.
    Response models:
        TestFailureAnalysisResponse, CodeQualityAnalysisResponse,
        PerformanceAnalysisResponse, plus their nested item types.
    LLMEmptyResponseError: raised when the LLM plane returns nothing usable.
"""

from __future__ import annotations

from coding_client.exceptions.pydantic_ai_exceptions import LLMEmptyResponseError
from coding_client.llm.base_agent import (
    BaseLLMAgent,
    close_llm_clients,
    last_failover_chain_id,
    last_inference_id,
)
from coding_client.llm.context import llm_request_context
from coding_client.llm.responses import (
    Bottleneck,
    CodeQualityAnalysisResponse,
    PerformanceAnalysisResponse,
    QualityIssue,
    TestFailureAnalysisResponse,
)
from coding_client.llm.routing import AGENT_ROUTING_REGISTRY, AgentRouting
from coding_client.llm.settings import LLMSettings, get_llm_settings

__all__ = [
    "AGENT_ROUTING_REGISTRY",
    "AgentRouting",
    "BaseLLMAgent",
    "Bottleneck",
    "CodeQualityAnalysisResponse",
    "LLMEmptyResponseError",
    "LLMSettings",
    "PerformanceAnalysisResponse",
    "QualityIssue",
    "TestFailureAnalysisResponse",
    "close_llm_clients",
    "get_llm_settings",
    "last_failover_chain_id",
    "last_inference_id",
    "llm_request_context",
]
