"""LLM client settings.

All env vars are read via pydantic-settings so callers can subclass or
override per-service. Production deployments inject these via the
the platform repo Deployment env block / SOPS secrets.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """Settings for LLM-plane access.

    Production points ``llm_api_base_url`` at inference-router; dev/bypass
    can point it at OpenAI, Ollama, LM Studio, or any other OpenAI-compatible
    endpoint.
    """

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    llm_api_base_url: str = Field(
        default="",
        description=(
            "OpenAI-compatible base URL. In production: the inference-router "
            "service URL. Required when llm_mode=='inference_router' and the "
            "service is actually wired up."
        ),
    )
    llm_api_key: str = Field(
        default="",
        description=(
            "API key for the OpenAI-compatible endpoint. Inference-router "
            "doesn't consume this; pydantic-ai/openai SDK requires non-empty."
        ),
    )
    llm_mode: Literal["inference_router", "direct"] = Field(
        default="inference_router",
        description="Plane mode: inference-router (provider chain) or direct.",
    )
    llm_api_timeout_seconds: float = Field(
        default=300.0,
        description="httpx timeout for LLM-plane calls (seconds).",
    )
    llm_routing_default_fallback_chain: str = Field(
        # Must name inference-router PROVIDERS, not models. The historical
        # "gemma,deepseek,claude" default named zero usable pairs: `gemma` is a
        # MODEL served by the `pgx-local` provider and is not a provider name in
        # the router catalog at all, and the `claude` provider ships
        # `enabled: false`. Both were therefore dropped at resolution and the
        # chain collapsed to the single hop ["deepseek"] — a "fallback chain"
        # with no fallback. `pgx-local,deepseek` mirrors inference-router's live
        # `default_chain: [pgx-local, deepseek]` (see the platform repo
        # clusters/strato/services/inference-router/providers-configmap.yaml):
        # free local vLLM primary, paid DeepSeek failover while pgx is DEGRADED.
        default="pgx-local,deepseek",
        description="Comma-separated default fallback chain for routing rules.",
    )
    model_registry_url: str = Field(
        default="",
        description=(
            "Base URL for model-registry — used by routing-rule bootstrap. "
            "Production injects via env var MODEL_REGISTRY_URL on the Deployment "
            "(see the platform configuration policy)."
        ),
    )

    @field_validator("llm_routing_default_fallback_chain")
    @classmethod
    def _strip_csv(cls, value: str) -> str:
        return value.strip()

    @property
    def fallback_chain_list(self) -> list[str]:
        """Parse the CSV fallback chain into a list."""
        raw = self.llm_routing_default_fallback_chain
        return [item.strip() for item in raw.split(",") if item.strip()]


_settings: LLMSettings | None = None


def get_llm_settings() -> LLMSettings:
    """Get LLMSettings singleton."""
    global _settings
    if _settings is None:
        _settings = LLMSettings()
    return _settings


def reset_llm_settings() -> None:
    """Reset the cached settings singleton (test helper)."""
    global _settings
    _settings = None
