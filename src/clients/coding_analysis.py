"""HTTP client for the coding-analysis service."""

from __future__ import annotations

import os
from typing import Any

from .base import ServiceClient

_ENV_VAR = "CODING_ANALYSIS_URL"


class CodingAnalysisClient(ServiceClient):
    """Client for coding-analysis endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        url = base_url or os.environ.get(_ENV_VAR, "")
        if not url:
            raise RuntimeError(
                f"CodingAnalysisClient requires base_url or {_ENV_VAR} env var. "
                "See the platform configuration policy."
            )
        super().__init__(url, timeout=timeout, max_retries=max_retries)

    async def analyze_code(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        return await self.post("/api/analysis/analyze", headers=headers, json=kwargs)

    async def get_analysis(
        self, analysis_id: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        return await self.get(f"/api/analysis/status/{analysis_id}", headers=headers, **kwargs)
