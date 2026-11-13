"""Tests for coding_client.config.base_settings.BaseMicroserviceSettings."""

from __future__ import annotations

import pytest
from coding_client.config.base_settings import BaseMicroserviceSettings
from pydantic_settings import SettingsConfigDict


class _Settings(BaseMicroserviceSettings):
    # Unique prefix so real env vars can't populate these fields.
    model_config = SettingsConfigDict(env_prefix="TEST_BS_", case_sensitive=False)
    _SERVICE_NAME = "coding-test"
    _REQUIRED_IN_PRODUCTION = ("foo_url", "bar_url")

    environment: str = "production"
    foo_url: str = ""
    bar_url: str = ""


class _UpperEnvSettings(BaseMicroserviceSettings):
    model_config = SettingsConfigDict(env_prefix="TEST_BS2_", case_sensitive=False)
    _SERVICE_NAME = "coding-upper"
    _ENV_ATTR = "ENVIRONMENT"
    _REQUIRED_IN_PRODUCTION = ("foo_url",)

    ENVIRONMENT: str = "production"
    foo_url: str = ""


class TestRequiredInProduction:
    def test_raises_when_missing_in_production(self):
        with pytest.raises(RuntimeError) as exc_info:
            _Settings(environment="production", foo_url="", bar_url="")
        msg = str(exc_info.value)
        assert "coding-test" in msg
        assert "foo_url" in msg
        assert "bar_url" in msg

    def test_lists_only_the_missing_fields(self):
        with pytest.raises(RuntimeError) as exc_info:
            _Settings(environment="production", foo_url="https://foo", bar_url="")
        msg = str(exc_info.value)
        assert "bar_url" in msg
        assert "foo_url" not in msg

    def test_passes_when_all_present_in_production(self):
        s = _Settings(environment="production", foo_url="https://foo", bar_url="https://bar")
        assert s.foo_url == "https://foo"

    def test_non_production_skips_check(self):
        s = _Settings(environment="development", foo_url="", bar_url="")
        assert s.environment == "development"


class TestEnvAttrOverride:
    def test_uppercase_env_attr_enforced(self):
        with pytest.raises(RuntimeError):
            _UpperEnvSettings(ENVIRONMENT="production", foo_url="")

    def test_uppercase_env_attr_non_prod_skips(self):
        s = _UpperEnvSettings(ENVIRONMENT="test", foo_url="")
        assert s.ENVIRONMENT == "test"


class TestEmptyRequirements:
    def test_default_empty_never_raises(self):
        class _Bare(BaseMicroserviceSettings):
            model_config = SettingsConfigDict(env_prefix="TEST_BS3_")
            environment: str = "production"

        # No _REQUIRED_IN_PRODUCTION → never raises.
        assert _Bare(environment="production").environment == "production"
