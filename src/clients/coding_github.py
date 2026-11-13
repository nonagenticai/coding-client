"""HTTP client for the coding-github service."""

from __future__ import annotations

import os
from typing import Any

from .base import ServiceClient

_ENV_VAR = "CODING_GITHUB_URL"


class CodingGitHubClient(ServiceClient):
    """Client for coding-github endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        url = base_url or os.environ.get(_ENV_VAR, "")
        if not url:
            raise RuntimeError(
                f"CodingGitHubClient requires base_url or {_ENV_VAR} env var. "
                "See the platform configuration policy."
            )
        super().__init__(url, timeout=timeout, max_retries=max_retries)

    # -- Repository management ------------------------------------------------

    async def list_repositories(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        """List all provisioned repositories."""
        return await self.get("/api/repositories/repositories", headers=headers, params=kwargs)

    async def import_repository(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        """Import a GitHub repository as a canonical workspace."""
        return await self.post("/api/repositories/import", headers=headers, json=kwargs)

    async def provision(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        """Compatibility alias for :meth:`import_repository`."""
        return await self.import_repository(headers=headers, **kwargs)

    async def get_status(
        self, container_name: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        """Get provisioning status for a specific container."""
        return await self.get(
            f"/api/repositories/status/{container_name}", headers=headers, params=kwargs
        )

    async def create_upstream_pr(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        """Create a pull request from the system fork to the user's original repo."""
        return await self.post("/api/repositories/create-upstream-pr", headers=headers, json=kwargs)

    # -- Pull request operations ----------------------------------------------

    async def fork(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        """Fork a repository."""
        return await self.post("/api/repositories/fork", headers=headers, json=kwargs)

    async def apply_changes(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        """Apply code changes to a forked repository."""
        return await self.post("/api/repositories/apply-changes", headers=headers, json=kwargs)

    async def create_pull_request(
        self, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        """Create a pull request."""
        return await self.post(
            "/api/repositories/create-pull-request", headers=headers, json=kwargs
        )

    async def validate_pull_request(
        self, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        """Validate a pull request."""
        return await self.post(
            "/api/repositories/validate-pull-request", headers=headers, json=kwargs
        )

    # -- File / tree operations -----------------------------------------------

    async def get_file(
        self, container_name: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        """Read a single file from a container repository."""
        return await self.get(
            f"/api/repositories/{container_name}/file", headers=headers, params=kwargs
        )

    async def get_tree(
        self, container_name: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        """Get the file tree for a container repository."""
        return await self.get(
            f"/api/repositories/{container_name}/tree", headers=headers, params=kwargs
        )

    async def get_directory(
        self, container_name: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        """List directory contents in a container repository."""
        return await self.get(
            f"/api/repositories/{container_name}/directory", headers=headers, params=kwargs
        )

    async def search(
        self, container_name: str, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> Any:
        """Search files in a container repository."""
        return await self.post(
            f"/api/repositories/{container_name}/search", headers=headers, json=kwargs
        )

    # -- Webhooks -------------------------------------------------------------

    async def create_webhook(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        """Register a GitHub webhook."""
        return await self.post("/api/repositories/webhooks/webhook", headers=headers, json=kwargs)

    # -- Backward-compatible aliases ------------------------------------------
    # These keep the old method names working with corrected paths.

    async def get_repo(self, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        """Alias for list_repositories (backward compatibility)."""
        return await self.list_repositories(headers=headers, **kwargs)
