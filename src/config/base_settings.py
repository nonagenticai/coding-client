"""Shared base settings for coding-* microservices.

Centralises the fail-loud-in-production pattern repeated across every service:
each service lists the env-var-backed fields that must be non-empty when
``ENVIRONMENT=production`` via ``_REQUIRED_IN_PRODUCTION``; this base raises a
single combined ``RuntimeError`` at startup if any are missing, instead of
silently routing traffic to a dead default.

Per ``the platform configuration policy``: service
addresses must come from gitops env, and missing env in production must crash
boot loudly.

Usage::

    class Settings(BaseMicroserviceSettings):
        model_config = SettingsConfigDict(env_prefix="CODING_FOO_")
        _SERVICE_NAME = "coding-foo"
        _REQUIRED_IN_PRODUCTION = ("database_url", "redis_url")

        environment: str = "production"
        database_url: str = ""
        redis_url: str = ""

Services whose environment field is named ``ENVIRONMENT`` (rather than
``environment``) set ``_ENV_ATTR = "ENVIRONMENT"``. Subclasses that need extra
post-init behaviour must call ``super().model_post_init(context)``.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic_settings import BaseSettings


class BaseMicroserviceSettings(BaseSettings):
    """Base settings providing required-in-production enforcement."""

    # ── Subclass-overridable contract ─────────────────────────────────
    # Fields (by attribute name) that must be non-empty in production.
    _REQUIRED_IN_PRODUCTION: ClassVar[tuple[str, ...]] = ()
    # Service name used in the missing-fields error message.
    _SERVICE_NAME: ClassVar[str] = "service"
    # Attribute that holds the environment string ("environment" or "ENVIRONMENT").
    _ENV_ATTR: ClassVar[str] = "environment"

    def model_post_init(self, __context: object) -> None:
        self._enforce_required_in_production()

    def _enforce_required_in_production(self) -> None:
        """Crash boot if any required field is empty in production."""
        environment = getattr(self, self._ENV_ATTR, "production")
        if environment != "production":
            return
        missing = [name for name in self._REQUIRED_IN_PRODUCTION if not getattr(self, name)]
        if missing:
            raise RuntimeError(
                f"{self._SERVICE_NAME} settings missing required fields in production: "
                f"{missing}. Set them via env vars on the Deployment "
                "(see the platform repo)."
            )
