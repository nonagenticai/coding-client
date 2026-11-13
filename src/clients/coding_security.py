"""HTTP client for the coding-security service."""

from __future__ import annotations

import os
from typing import Any

from .base import ServiceClient

_ENV_VAR = "CODING_SECURITY_URL"


class CodingSecurityClient(ServiceClient):
    """Client for coding-security endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        url = base_url or os.environ.get(_ENV_VAR, "")
        if not url:
            raise RuntimeError(
                f"CodingSecurityClient requires base_url or {_ENV_VAR} env var. "
                "See the platform configuration policy."
            )
        super().__init__(url, timeout=timeout, max_retries=max_retries)

    async def scan(
        self, container_name: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        return await self.post(f"/api/security/scan/{container_name}", headers=headers, json=kwargs)

    async def get_scan_results(
        self, container_name: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        return await self.get(f"/api/security/report/{container_name}", headers=headers, **kwargs)

    async def analyze_vulnerabilities(
        self,
        file_paths: list[str],
        max_files: int = 20,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> Any:
        return await self.post(
            "/api/security/analyze-vulnerabilities",
            headers=headers,
            json={"file_paths": file_paths, "max_files": max_files, **kwargs},
        )
