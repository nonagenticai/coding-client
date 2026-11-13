"""HTTP client for the coding-realtime service."""

from __future__ import annotations

import os
from typing import Any

from .base import ServiceClient

_ENV_VAR = "CODING_REALTIME_URL"


class CodingRealtimeClient(ServiceClient):
    """Client for coding-realtime endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        url = base_url or os.environ.get(_ENV_VAR, "")
        if not url:
            raise RuntimeError(
                f"CodingRealtimeClient requires base_url or {_ENV_VAR} env var. "
                "See the platform configuration policy."
            )
        super().__init__(url, timeout=timeout, max_retries=max_retries)

    # -- Broadcast / messaging ------------------------------------------------

    async def broadcast(
        self,
        *,
        event_type: str,
        data: dict[str, Any],
        priority: str = "normal",
        container_name: str | None = None,
        tags: list[str] | None = None,
        correlation_id: str | None = None,
        ttl_seconds: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Publish a broadcast to all subscribers of a container.

        POSTs to ``/api/broadcast/publish`` — the REST publish endpoint (D9).
        (The old helper posted to ``/api/broadcast/subscribe``, a WebSocket-only
        route, so every broadcast 404'd and was silently dropped.)

        ``container_name`` may be omitted when ``data`` carries it as
        ``data['container_name']`` (the shape coding-containers' lifecycle events
        already use). Tenant-scoped: pass the owning tenant as
        ``headers={'X-Tenant-Id': ...}`` so the publish resolves to the container's
        owner (BOLA — the server rejects a container the tenant does not own).

        Returns the publish result, including ``delivered`` and
        ``subscriber_count`` so the caller can distinguish a real fan-out from a
        no-op (no subscribers).
        """
        payload: dict[str, Any] = {
            "event_type": event_type,
            "data": data,
            "priority": priority,
        }
        if container_name is not None:
            payload["container_name"] = container_name
        if tags is not None:
            payload["tags"] = tags
        if correlation_id is not None:
            payload["correlation_id"] = correlation_id
        if ttl_seconds is not None:
            payload["ttl_seconds"] = ttl_seconds
        return await self.post("/api/broadcast/publish", headers=headers, json=payload)

    # -- Stats / monitoring ---------------------------------------------------

    async def get_global_stats(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        """Get global rate-limiter statistics across all containers."""
        return await self.get("/api/global-stats", headers=headers, params=kwargs)

    async def get_stats(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        """Get rate-limit stats for all containers."""
        return await self.get("/api/stats", headers=headers, params=kwargs)

    async def get_container_stats(
        self, container_name: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        """Get rate-limit stats for a specific container."""
        return await self.get(f"/api/stats/{container_name}", headers=headers, params=kwargs)

    async def get_violations(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        """Get rate-limit violations."""
        return await self.get("/api/violations", headers=headers, params=kwargs)

    # -- Connection / health --------------------------------------------------

    async def get_connections(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        """Get active realtime analysis connections."""
        return await self.get("/api/realtime/connections", headers=headers, params=kwargs)

    async def get_global_health(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        """Get global WebSocket health statistics."""
        return await self.get("/api/ws-health/global", headers=headers, params=kwargs)

    async def get_container_health(
        self, container_name: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        """Get WebSocket health statistics for a specific container."""
        return await self.get(
            f"/api/ws-health/container/{container_name}", headers=headers, params=kwargs
        )

    async def get_containers_health(
        self, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        """Get health statistics for all containers."""
        return await self.get("/api/ws-health/containers", headers=headers, params=kwargs)

    async def cleanup_stale(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        """Trigger cleanup of stale WebSocket connections."""
        return await self.post("/api/ws-health/cleanup", headers=headers, json=kwargs)

    # -- Health ---------------------------------------------------------------

    async def health(self, **kwargs: Any) -> Any:
        """Service-level health check."""
        return await self.get("/api/health/live", **kwargs)
