"""HTTP client for the coding-testing service."""

from __future__ import annotations

import os
from typing import Any

from .base import ServiceClient

_ENV_VAR = "CODING_TESTING_URL"


class CodingTestingClient(ServiceClient):
    """Client for coding-testing endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        url = base_url or os.environ.get(_ENV_VAR, "")
        if not url:
            raise RuntimeError(
                f"CodingTestingClient requires base_url or {_ENV_VAR} env var. "
                "See the platform configuration policy."
            )
        super().__init__(url, timeout=timeout, max_retries=max_retries)

    async def run_tests(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        return await self.post("/api/tests/execute", headers=headers, json=kwargs)
