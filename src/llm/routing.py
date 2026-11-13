"""Routing-rule registry for coding-* LLM agents.

Each entry maps a stable ``schema_id`` to its pydantic response model and
optional fallback chain override. ``scripts/register_routing_rules.py``
iterates this registry on deploy and PUTs each rule into model-registry so
that inference-router can route + fall back per schema_id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from coding_client.llm.responses import (
    CodeQualityAnalysisResponse,
    PerformanceAnalysisResponse,
    TestFailureAnalysisResponse,
)
from pydantic import BaseModel


@dataclass(frozen=True)
class AgentRouting:
    """Routing config for a single coding-* LLM agent."""

    schema_id: str
    response_model: type[BaseModel]
    fallback_chain: list[str] | None = field(default=None)
    system_prompt: str = field(default="")


AGENT_ROUTING_REGISTRY: dict[str, AgentRouting] = {
    "test_failure_analysis": AgentRouting(
        schema_id="test_failure_analysis",
        response_model=TestFailureAnalysisResponse,
        system_prompt=(
            "You are a senior test engineer. Diagnose the failed test and "
            "return a structured root cause, fix, confidence, and category."
        ),
    ),
    "code_quality_analysis": AgentRouting(
        schema_id="code_quality_analysis",
        response_model=CodeQualityAnalysisResponse,
        system_prompt=(
            "You are a senior code reviewer. Identify quality issues with "
            "severity, category, description, and an optional refactor."
        ),
    ),
    "performance_analysis": AgentRouting(
        schema_id="performance_analysis",
        response_model=PerformanceAnalysisResponse,
        system_prompt=(
            "You are a performance engineer. Identify bottlenecks and "
            "propose concrete optimisations."
        ),
    ),
}


def build_routing_rule_payload(
    routing: AgentRouting,
    *,
    default_fallback_chain: list[str],
) -> dict[str, Any]:
    """Build the model-registry PUT body for one routing rule.

    Mirrors ``UpdateRoutingRequest`` in model-registry. Endpoint is
    ``PUT /api/routing/{schema_id}`` — see the bootstrap script.
    """
    chain = list(routing.fallback_chain or default_fallback_chain)
    if not chain:
        raise ValueError(f"AgentRouting {routing.schema_id} resolved to an empty fallback chain")
    return {
        "fallback_chain": chain,
        "json_schema": routing.response_model.model_json_schema(),
        "system_prompt": routing.system_prompt,
    }


def build_routing_rule_url(base_url: str, schema_id: str) -> str:
    """Build the model-registry endpoint URL for one routing rule."""
    return f"{base_url.rstrip('/')}/api/routing/{schema_id}"
