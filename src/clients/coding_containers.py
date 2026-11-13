"""Legacy container-named client for the coding-containers service."""

from __future__ import annotations

import os
from typing import Any

from .base import ServiceClient

_ENV_VAR = "CODING_CONTAINERS_URL"


class CodingContainersClient(ServiceClient):
    """Compatibility client for the legacy ``/api/containers`` aliases.

    New callers should use :class:`CodingWorkspacesClient`. This class remains
    available so existing consumers can migrate without a flag day.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        url = base_url or os.environ.get(_ENV_VAR, "")
        if not url:
            raise RuntimeError(
                f"CodingContainersClient requires base_url or {_ENV_VAR} env var. "
                "See the platform configuration policy."
            )
        super().__init__(url, timeout=timeout, max_retries=max_retries)

    async def create_container(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        return await self.post("/api/containers", headers=headers, json=kwargs)

    async def get_container(
        self, container_name: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        return await self.get(f"/api/containers/{container_name}", headers=headers, **kwargs)

    async def delete_container(
        self, container_name: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        return await self.delete(f"/api/containers/{container_name}", headers=headers, **kwargs)
