"""Tests for coding_client.llm.settings."""

from __future__ import annotations

import pytest
from coding_client.llm.settings import LLMSettings, get_llm_settings, reset_llm_settings


@pytest.fixture(autouse=True)
def _reset_settings():
    reset_llm_settings()
    yield
    reset_llm_settings()


def test_defaults(monkeypatch):
    for key in (
        "LLM_API_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODE",
        "LLM_API_TIMEOUT_SECONDS",
        "LLM_ROUTING_DEFAULT_FALLBACK_CHAIN",
        "MODEL_REGISTRY_URL",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = LLMSettings()
    assert settings.llm_api_base_url == ""
    assert settings.llm_api_key == ""
    assert settings.llm_mode == "inference_router"
    assert settings.llm_api_timeout_seconds == 300.0
    assert settings.fallback_chain_list == ["pgx-local", "deepseek"]
    # model_registry_url has no hardcoded default per the config-externalization
    # policy; production injects MODEL_REGISTRY_URL via the Deployment env block.
    assert settings.model_registry_url == ""


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LLM_API_BASE_URL", "http://router:8000/v1")
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_MODE", "direct")
    monkeypatch.setenv("LLM_API_TIMEOUT_SECONDS", "42")
    monkeypatch.setenv("LLM_ROUTING_DEFAULT_FALLBACK_CHAIN", "a, b ,c")

    settings = LLMSettings()
    assert settings.llm_api_base_url == "http://router:8000/v1"
    assert settings.llm_api_key == "secret"
    assert settings.llm_mode == "direct"
    assert settings.llm_api_timeout_seconds == 42.0
    assert settings.fallback_chain_list == ["a", "b", "c"]


def test_invalid_mode_rejected(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "nonsense")
    with pytest.raises(Exception):  # noqa: B017,PT011 — pydantic ValidationError
        LLMSettings()


def test_singleton(monkeypatch):
    monkeypatch.setenv("LLM_API_BASE_URL", "http://x")
    a = get_llm_settings()
    b = get_llm_settings()
    assert a is b


# Providers declared in inference-router's catalog
# (the platform's inference-router providers configmap).
# `gemma` is deliberately absent: it is a MODEL served by `pgx-local`, never a
# provider name. `claude` is present but ships `enabled: false`.
ROUTER_ENABLED_PROVIDERS = frozenset({"pgx-local", "deepseek", "xai"})
ROUTER_DISABLED_PROVIDERS = frozenset({"claude"})


def test_default_chain_is_routable_multi_hop(monkeypatch):
    """The SHIPPED default must be >=2 distinct, real, ENABLED providers.

    Regression pin. The previous default "gemma,deepseek,claude" named zero
    usable pairs: `gemma` is not a provider name at all (it is the model
    pgx-local serves) and `claude` is `enabled: false`. Both were dropped at
    resolution, collapsing the chain to the single hop ["deepseek"] — no
    failover. model-registry now rejects such a chain at registration with
    HTTP 422, so a regression here breaks the nightly coding-llm-bootstrap Job.
    """
    monkeypatch.delenv("LLM_ROUTING_DEFAULT_FALLBACK_CHAIN", raising=False)
    chain = LLMSettings().fallback_chain_list

    unknown = [p for p in chain if p not in ROUTER_ENABLED_PROVIDERS | ROUTER_DISABLED_PROVIDERS]
    assert not unknown, f"chain names non-providers (models?): {unknown}"

    disabled = [p for p in chain if p in ROUTER_DISABLED_PROVIDERS]
    assert not disabled, f"chain names disabled providers: {disabled}"

    assert len(set(chain)) == len(chain), f"chain has duplicate hops: {chain}"
    assert len(set(chain)) >= 2, f"chain has no failover hop: {chain}"


def test_default_chain_matches_router_default_chain(monkeypatch):
    """Pin the exact value against inference-router's live `default_chain`."""
    monkeypatch.delenv("LLM_ROUTING_DEFAULT_FALLBACK_CHAIN", raising=False)
    assert LLMSettings().fallback_chain_list == ["pgx-local", "deepseek"]
