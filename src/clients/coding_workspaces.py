"""HTTP client for canonical repository-workspace operations."""

from __future__ import annotations

import os
from typing import Any

from .base import ServiceClient

_ENV_VAR = "CODING_CONTAINERS_URL"


class CodingWorkspacesClient(ServiceClient):
    """Client for workspaces owned by the coding-containers service.

    A workspace is a checked-out GitHub repository plus its isolated runtime.
    The runtime may be Docker or Kubernetes, so callers should use this client
    instead of coupling domain operations to the legacy container API.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        url = base_url or os.environ.get(_ENV_VAR, "")
        if not url:
            raise RuntimeError(
                f"CodingWorkspacesClient requires base_url or {_ENV_VAR} env var. "
                "See the platform configuration policy."
            )
        super().__init__(url, timeout=timeout, max_retries=max_retries)

    async def list_workspaces(self, headers: dict[str, str] | None = None, **filters: Any) -> Any:
        return await self.get("/api/workspaces/", headers=headers, params=filters)

    async def create_workspace(
        self, headers: dict[str, str] | None = None, **workspace: Any
    ) -> Any:
        return await self.post("/api/workspaces/", headers=headers, json=workspace)

    async def get_workspace(
        self, workspace_name: str, headers: dict[str, str] | None = None
    ) -> Any:
        return await self.get(f"/api/workspaces/{workspace_name}", headers=headers)

    async def get_status(self, workspace_name: str, headers: dict[str, str] | None = None) -> Any:
        return await self.get(f"/api/workspaces/{workspace_name}/status", headers=headers)

    async def delete_workspace(
        self,
        workspace_name: str,
        headers: dict[str, str] | None = None,
        **options: Any,
    ) -> Any:
        return await self.delete(
            f"/api/workspaces/{workspace_name}", headers=headers, params=options
        )

    async def delete_all_workspaces(self, headers: dict[str, str] | None = None) -> Any:
        return await self.delete("/api/workspaces/all", headers=headers)

    async def list_files(
        self,
        workspace_name: str,
        headers: dict[str, str] | None = None,
        **query: Any,
    ) -> Any:
        return await self.get(
            f"/api/workspaces/{workspace_name}/files", headers=headers, params=query
        )

    async def create_directory(
        self, workspace_name: str, headers: dict[str, str] | None = None, **body: Any
    ) -> Any:
        return await self.post(
            f"/api/workspaces/{workspace_name}/mkdir", headers=headers, json=body
        )

    async def create_file(
        self, workspace_name: str, headers: dict[str, str] | None = None, **body: Any
    ) -> Any:
        return await self.post(
            f"/api/workspaces/{workspace_name}/touch", headers=headers, json=body
        )

    async def write_file(
        self, workspace_name: str, headers: dict[str, str] | None = None, **body: Any
    ) -> Any:
        return await self.post(
            f"/api/workspaces/{workspace_name}/write-file", headers=headers, json=body
        )

    async def move_path(
        self, workspace_name: str, headers: dict[str, str] | None = None, **body: Any
    ) -> Any:
        return await self.post(f"/api/workspaces/{workspace_name}/move", headers=headers, json=body)

    async def delete_path(
        self,
        workspace_name: str,
        headers: dict[str, str] | None = None,
        **query: Any,
    ) -> Any:
        return await self.delete(
            f"/api/workspaces/{workspace_name}/files", headers=headers, params=query
        )

    async def get_git_status(
        self, workspace_name: str, headers: dict[str, str] | None = None
    ) -> Any:
        return await self.get(f"/api/workspaces/{workspace_name}/git/status", headers=headers)

    async def commit(
        self, workspace_name: str, headers: dict[str, str] | None = None, **body: Any
    ) -> Any:
        return await self.post(
            f"/api/workspaces/{workspace_name}/git/commit", headers=headers, json=body
        )

    async def push(
        self, workspace_name: str, headers: dict[str, str] | None = None, **body: Any
    ) -> Any:
        return await self.post(
            f"/api/workspaces/{workspace_name}/git/push", headers=headers, json=body
        )

    async def exec(
        self, workspace_name: str, headers: dict[str, str] | None = None, **body: Any
    ) -> Any:
        return await self.post(f"/api/workspaces/{workspace_name}/exec", headers=headers, json=body)

    async def install_dependencies(
        self, workspace_name: str, headers: dict[str, str] | None = None, **body: Any
    ) -> Any:
        return await self.post(
            f"/api/workspaces/{workspace_name}/install-dependencies",
            headers=headers,
            json=body,
        )

    async def get_dependency_status(
        self, workspace_name: str, headers: dict[str, str] | None = None
    ) -> Any:
        return await self.get(
            f"/api/workspaces/{workspace_name}/dependency-status", headers=headers
        )

    async def package_upgrade(
        self, workspace_name: str, headers: dict[str, str] | None = None, **body: Any
    ) -> Any:
        return await self.post(
            f"/api/workspaces/{workspace_name}/package-upgrade", headers=headers, json=body
        )

    async def package_modify(
        self, workspace_name: str, headers: dict[str, str] | None = None, **body: Any
    ) -> Any:
        return await self.post(
            f"/api/workspaces/{workspace_name}/package-modify", headers=headers, json=body
        )

    async def execute_agent(
        self, workspace_name: str, headers: dict[str, str] | None = None, **body: Any
    ) -> Any:
        return await self.post(
            f"/api/workspaces/{workspace_name}/execute-agent", headers=headers, json=body
        )

    async def get_agent_capabilities(
        self, workspace_name: str, headers: dict[str, str] | None = None
    ) -> Any:
        return await self.get(
            f"/api/workspaces/{workspace_name}/agent-capabilities", headers=headers
        )

    # ------------------------------------------------------------------
    # Async exec jobs (coding-containers ``src/routers/exec_async.py``)
    # ------------------------------------------------------------------

    async def exec_async(
        self,
        workspace_name: str,
        command: list[str],
        workdir: str | None = None,
        timeout: int | None = None,
        callback_url: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Start ``command`` as an async job: ``POST {ws}/exec/async`` (202).

        Returns the accepted document (``job_id``, ``container_name``, ``status``,
        ``links.status``). ``timeout`` is the job's wall-clock limit in seconds
        (server range 1-14400, default 3600), not the HTTP timeout. Omitted
        arguments are not sent, so the server's defaults apply.

        Sent exactly once (no transport retry): a retried POST without
        ``callback_url`` would start a second job. With ``callback_url`` the
        server de-duplicates a replay itself (same ``job_id``).
        """
        body: dict[str, Any] = {"command": command}
        if workdir is not None:
            body["workdir"] = workdir
        if timeout is not None:
            body["timeout"] = timeout
        if callback_url is not None:
            body["callback_url"] = callback_url
        return await self.post(
            f"/api/workspaces/{workspace_name}/exec/async",
            headers=headers,
            json=body,
            max_attempts=1,
        )

    async def get_exec_job(
        self, workspace_name: str, job_id: str, headers: dict[str, str] | None = None
    ) -> Any:
        """Read an async exec job: ``GET {ws}/exec/jobs/{job_id}``.

        Status is ``queued | running | completed | failed``; a job of another
        tenant or workspace is a 404 (:class:`ServiceError`).
        """
        return await self.get(
            f"/api/workspaces/{workspace_name}/exec/jobs/{job_id}", headers=headers
        )

    # ------------------------------------------------------------------
    # Secondary read-only repositories
    # (coding-containers ``src/routers/containers/secondary_repos.py``)
    # ------------------------------------------------------------------

    async def add_repo(
        self,
        workspace_name: str,
        repo_url: str,
        ref: str | None = None,
        refresh: bool = False,
        headers: dict[str, str] | None = None,
        request_timeout: float | None = None,
    ) -> Any:
        """Check out a read-only secondary repository: ``POST {ws}/repos``.

        ``repo_url`` is ``https://github.com/<owner>/<repo>`` or ``<owner>/<repo>``;
        ``ref`` a branch, tag or full commit SHA (default: the repository's default
        branch). The checkout lands at ``/workspace/.repos/<owner>__<repo>`` (the
        response's ``path``) and is always read-only: it has no remote and no push
        credential. ``request_timeout`` overrides the client's HTTP timeout for a
        large clone.
        """
        body: dict[str, Any] = {"repo_url": repo_url}
        if ref is not None:
            body["ref"] = ref
        if refresh:
            body["refresh"] = True
        kwargs: dict[str, Any] = {}
        if request_timeout is not None:
            kwargs["timeout"] = request_timeout
        return await self.post(
            f"/api/workspaces/{workspace_name}/repos", headers=headers, json=body, **kwargs
        )

    async def list_repos(self, workspace_name: str, headers: dict[str, str] | None = None) -> Any:
        """List the workspace's secondary repositories: ``GET {ws}/repos``."""
        return await self.get(f"/api/workspaces/{workspace_name}/repos", headers=headers)
