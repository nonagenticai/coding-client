"""Tests for service-specific clients in coding_client.clients."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from coding_client.clients.base import ServiceError
from coding_client.clients.coding_ai import CodingAIClient
from coding_client.clients.coding_analysis import CodingAnalysisClient
from coding_client.clients.coding_containers import CodingContainersClient
from coding_client.clients.coding_github import CodingGitHubClient
from coding_client.clients.coding_realtime import CodingRealtimeClient
from coding_client.clients.coding_security import CodingSecurityClient
from coding_client.clients.coding_testing import CodingTestingClient
from coding_client.clients.coding_workspaces import CodingWorkspacesClient

# ---------------------------------------------------------------------------
# CodingAIClient (port 8690, env CODING_AI_URL, timeout 60)
# ---------------------------------------------------------------------------


class TestCodingAIClient:
    """Test CodingAIClient URL resolution and methods."""

    def test_url_from_env(self):
        # Autouse fixture sets CODING_AI_URL; constructor should read it.
        client = CodingAIClient()
        assert client.base_url == "http://coding-ai:8690"

    def test_raises_when_no_url_configured(self, monkeypatch):
        monkeypatch.delenv("CODING_AI_URL", raising=False)
        with pytest.raises(RuntimeError, match="CODING_AI_URL"):
            CodingAIClient()

    def test_custom_url(self):
        client = CodingAIClient(base_url="http://localhost:9999")
        assert client.base_url == "http://localhost:9999"

    def test_env_url(self):
        with patch.dict("os.environ", {"CODING_AI_URL": "http://env-ai:1111"}):
            client = CodingAIClient()
            assert client.base_url == "http://env-ai:1111"

    def test_custom_url_takes_precedence_over_env(self):
        with patch.dict("os.environ", {"CODING_AI_URL": "http://env-ai:1111"}):
            client = CodingAIClient(base_url="http://explicit:2222")
            assert client.base_url == "http://explicit:2222"

    def test_default_timeout(self):
        client = CodingAIClient()
        assert client.timeout == 60.0

    async def test_analyze_failure(self):
        client = CodingAIClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"analysis": "fix"}
            result = await client.analyze_failure(error="SyntaxError", traceback="line 1")
            mock_post.assert_called_once_with(
                "/api/ai/analysis/tests/failure-analysis",
                headers=None,
                json={"error": "SyntaxError", "traceback": "line 1"},
            )
            assert result == {"analysis": "fix"}


# ---------------------------------------------------------------------------
# CodingAnalysisClient (port 8688, env CODING_ANALYSIS_URL, timeout 30)
# ---------------------------------------------------------------------------


class TestCodingAnalysisClient:
    """Test CodingAnalysisClient URL resolution and methods."""

    def test_url_from_env(self):
        client = CodingAnalysisClient()
        assert client.base_url == "http://coding-analysis:8688"

    def test_raises_when_no_url_configured(self, monkeypatch):
        monkeypatch.delenv("CODING_ANALYSIS_URL", raising=False)
        with pytest.raises(RuntimeError, match="CODING_ANALYSIS_URL"):
            CodingAnalysisClient()

    def test_custom_url(self):
        client = CodingAnalysisClient(base_url="http://local:7777")
        assert client.base_url == "http://local:7777"

    def test_env_url(self):
        with patch.dict("os.environ", {"CODING_ANALYSIS_URL": "http://env-analysis:3333"}):
            client = CodingAnalysisClient()
            assert client.base_url == "http://env-analysis:3333"

    def test_default_timeout(self):
        client = CodingAnalysisClient()
        assert client.timeout == 30.0

    async def test_analyze_code(self):
        client = CodingAnalysisClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"id": "a1"}
            result = await client.analyze_code(code="print(1)", language="python")
            mock_post.assert_called_once_with(
                "/api/analysis/analyze",
                headers=None,
                json={"code": "print(1)", "language": "python"},
            )
            assert result == {"id": "a1"}

    async def test_get_analysis(self):
        client = CodingAnalysisClient()
        with patch.object(client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"status": "done"}
            result = await client.get_analysis("a1")
            mock_get.assert_called_once_with("/api/analysis/status/a1", headers=None)
            assert result == {"status": "done"}


# ---------------------------------------------------------------------------
# CodingContainersClient (port 8691, env CODING_CONTAINERS_URL, timeout 30)
# ---------------------------------------------------------------------------


class TestCodingContainersClient:
    """Test CodingContainersClient URL resolution and methods."""

    def test_url_from_env(self):
        client = CodingContainersClient()
        assert client.base_url == "http://coding-containers:8691"

    def test_raises_when_no_url_configured(self, monkeypatch):
        monkeypatch.delenv("CODING_CONTAINERS_URL", raising=False)
        with pytest.raises(RuntimeError, match="CODING_CONTAINERS_URL"):
            CodingContainersClient()

    def test_custom_url(self):
        client = CodingContainersClient(base_url="http://local:4444")
        assert client.base_url == "http://local:4444"

    def test_env_url(self):
        with patch.dict("os.environ", {"CODING_CONTAINERS_URL": "http://env-c:5555"}):
            client = CodingContainersClient()
            assert client.base_url == "http://env-c:5555"

    async def test_create_container(self):
        client = CodingContainersClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"name": "ctr-1"}
            result = await client.create_container(image="python:3.13", memory="512m")
            mock_post.assert_called_once_with(
                "/api/containers",
                headers=None,
                json={"image": "python:3.13", "memory": "512m"},
            )
            assert result == {"name": "ctr-1"}

    async def test_get_container(self):
        client = CodingContainersClient()
        with patch.object(client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"status": "running"}
            result = await client.get_container("ctr-1")
            mock_get.assert_called_once_with("/api/containers/ctr-1", headers=None)
            assert result == {"status": "running"}

    async def test_delete_container(self):
        client = CodingContainersClient()
        with patch.object(client, "delete", new_callable=AsyncMock) as mock_del:
            mock_del.return_value = None
            result = await client.delete_container("ctr-1")
            mock_del.assert_called_once_with("/api/containers/ctr-1", headers=None)
            assert result is None


# ---------------------------------------------------------------------------
# CodingWorkspacesClient (canonical workspace API on port 8691)
# ---------------------------------------------------------------------------


class TestCodingWorkspacesClient:
    def test_url_from_env(self):
        client = CodingWorkspacesClient()
        assert client.base_url == "http://coding-containers:8691"

    async def test_workspace_lifecycle_paths(self):
        client = CodingWorkspacesClient()
        with (
            patch.object(client, "post", new_callable=AsyncMock) as mock_post,
            patch.object(client, "get", new_callable=AsyncMock) as mock_get,
            patch.object(client, "delete", new_callable=AsyncMock) as mock_delete,
        ):
            await client.create_workspace(repo_url="https://github.com/acme/example")
            await client.get_workspace("example-1")
            await client.delete_workspace("example-1", force=True)

            mock_post.assert_awaited_once_with(
                "/api/workspaces/",
                headers=None,
                json={"repo_url": "https://github.com/acme/example"},
            )
            mock_get.assert_awaited_once_with("/api/workspaces/example-1", headers=None)
            mock_delete.assert_awaited_once_with(
                "/api/workspaces/example-1", headers=None, params={"force": True}
            )

    async def test_workspace_operation_paths(self):
        client = CodingWorkspacesClient()
        with (
            patch.object(client, "post", new_callable=AsyncMock) as mock_post,
            patch.object(client, "get", new_callable=AsyncMock) as mock_get,
        ):
            await client.exec("example-1", command=["git", "status"])
            await client.list_files("example-1", path="src")

            mock_post.assert_awaited_once_with(
                "/api/workspaces/example-1/exec",
                headers=None,
                json={"command": ["git", "status"]},
            )
            mock_get.assert_awaited_once_with(
                "/api/workspaces/example-1/files", headers=None, params={"path": "src"}
            )


class TestCodingWorkspacesAsyncExecAndRepos:
    """py2rust A2 (coding-client#65): async exec jobs + secondary read-only repos."""

    async def test_exec_async_minimal_body_single_attempt(self):
        client = CodingWorkspacesClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"job_id": "j1", "status": "queued"}
            result = await client.exec_async("ws-1", ["cargo", "build"])
            assert result == {"job_id": "j1", "status": "queued"}
            mock_post.assert_awaited_once_with(
                "/api/workspaces/ws-1/exec/async",
                headers=None,
                json={"command": ["cargo", "build"]},
                max_attempts=1,
            )

    async def test_exec_async_full_body(self):
        client = CodingWorkspacesClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            await client.exec_async(
                "ws-1",
                ["cargo", "nextest", "run"],
                workdir="/workspace/.repos/acme__lib",
                timeout=7200,
                callback_url="http://n8n:5678/webhook-waiting/1",
                headers={"X-Tenant-ID": "t1"},
            )
            mock_post.assert_awaited_once_with(
                "/api/workspaces/ws-1/exec/async",
                headers={"X-Tenant-ID": "t1"},
                json={
                    "command": ["cargo", "nextest", "run"],
                    "workdir": "/workspace/.repos/acme__lib",
                    "timeout": 7200,
                    "callback_url": "http://n8n:5678/webhook-waiting/1",
                },
                max_attempts=1,
            )

    async def test_get_exec_job_path(self):
        client = CodingWorkspacesClient()
        with patch.object(client, "get", new_callable=AsyncMock) as mock_get:
            await client.get_exec_job("ws-1", "0190-abc")
            mock_get.assert_awaited_once_with(
                "/api/workspaces/ws-1/exec/jobs/0190-abc", headers=None
            )

    async def test_add_repo_minimal(self):
        client = CodingWorkspacesClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            await client.add_repo("ws-1", "acme/lib")
            mock_post.assert_awaited_once_with(
                "/api/workspaces/ws-1/repos", headers=None, json={"repo_url": "acme/lib"}
            )

    async def test_add_repo_full(self):
        client = CodingWorkspacesClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            await client.add_repo(
                "ws-1",
                "https://github.com/acme/lib",
                ref="v1.2.0",
                refresh=True,
                request_timeout=300.0,
            )
            mock_post.assert_awaited_once_with(
                "/api/workspaces/ws-1/repos",
                headers=None,
                json={"repo_url": "https://github.com/acme/lib", "ref": "v1.2.0", "refresh": True},
                timeout=300.0,
            )

    async def test_list_repos_path(self):
        client = CodingWorkspacesClient()
        with patch.object(client, "get", new_callable=AsyncMock) as mock_get:
            await client.list_repos("ws-1")
            mock_get.assert_awaited_once_with("/api/workspaces/ws-1/repos", headers=None)

    @staticmethod
    def _client_with_transport(handler) -> CodingWorkspacesClient:
        client = CodingWorkspacesClient(base_url="http://cc:8691", max_retries=3)
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(handler)
        )
        return client

    async def test_exec_async_is_not_retried_on_read_timeout(self):
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            raise httpx.ReadTimeout("slow", request=request)

        client = self._client_with_transport(handler)
        with pytest.raises(httpx.ReadTimeout):
            await client.exec_async("ws-1", ["cargo", "build"])
        assert len(calls) == 1
        await client.close()

    async def test_exec_async_202_over_http(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert request.url.path == "/api/workspaces/ws-1/exec/async"
            assert json.loads(request.content) == {"command": ["cargo", "build"], "timeout": 60}
            return httpx.Response(
                202,
                json={
                    "job_id": "j1",
                    "container_name": "ws-1",
                    "status": "queued",
                    "links": {"status": "/api/workspaces/ws-1/exec/jobs/j1"},
                },
            )

        client = self._client_with_transport(handler)
        result = await client.exec_async("ws-1", ["cargo", "build"], timeout=60)
        assert result["job_id"] == "j1"
        assert result["links"]["status"] == "/api/workspaces/ws-1/exec/jobs/j1"
        await client.close()

    async def test_get_exec_job_retries_on_read_timeout(self):
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if len(calls) == 1:
                raise httpx.ReadTimeout("slow", request=request)
            return httpx.Response(200, json={"job_id": "j1", "status": "running"})

        client = self._client_with_transport(handler)
        result = await client.get_exec_job("ws-1", "j1")
        assert result == {"job_id": "j1", "status": "running"}
        assert len(calls) == 2
        await client.close()

    async def test_get_exec_job_404_raises_service_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"detail": "Exec job not found"})

        client = self._client_with_transport(handler)
        with pytest.raises(ServiceError) as exc_info:
            await client.get_exec_job("ws-1", "j1")
        assert exc_info.value.status_code == 404
        await client.close()


# ---------------------------------------------------------------------------
# CodingGitHubClient (port 8692, env CODING_GITHUB_URL, timeout 30)
# ---------------------------------------------------------------------------


class TestCodingGitHubClient:
    """Test CodingGitHubClient URL resolution and methods."""

    def test_url_from_env(self):
        client = CodingGitHubClient()
        assert client.base_url == "http://coding-github:8692"

    def test_raises_when_no_url_configured(self, monkeypatch):
        monkeypatch.delenv("CODING_GITHUB_URL", raising=False)
        with pytest.raises(RuntimeError, match="CODING_GITHUB_URL"):
            CodingGitHubClient()

    def test_custom_url(self):
        client = CodingGitHubClient(base_url="http://local:6666")
        assert client.base_url == "http://local:6666"

    def test_env_url(self):
        with patch.dict("os.environ", {"CODING_GITHUB_URL": "http://env-gh:7777"}):
            client = CodingGitHubClient()
            assert client.base_url == "http://env-gh:7777"

    async def test_get_repo(self):
        client = CodingGitHubClient()
        with patch.object(client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"name": "my-repo", "stars": 42}
            result = await client.get_repo(owner="org", repo="my-repo")
            mock_get.assert_called_once_with(
                "/api/repositories/repositories",
                headers=None,
                params={"owner": "org", "repo": "my-repo"},
            )
            assert result == {"name": "my-repo", "stars": 42}

    async def test_create_webhook(self):
        client = CodingGitHubClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"id": "wh-1"}
            result = await client.create_webhook(url="https://cb.example.com", events=["push"])
            mock_post.assert_called_once_with(
                "/api/repositories/webhooks/webhook",
                headers=None,
                json={"url": "https://cb.example.com", "events": ["push"]},
            )
            assert result == {"id": "wh-1"}

    async def test_import_repository_uses_canonical_route(self):
        client = CodingGitHubClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            await client.import_repository(repo_url="https://github.com/org/repo")
            mock_post.assert_called_once_with(
                "/api/repositories/import",
                headers=None,
                json={"repo_url": "https://github.com/org/repo"},
            )

    async def test_provision_is_import_compatibility_alias(self):
        client = CodingGitHubClient()
        with patch.object(client, "import_repository", new_callable=AsyncMock) as mock_import:
            await client.provision(repo_url="https://github.com/org/repo")
            mock_import.assert_awaited_once_with(
                headers=None,
                repo_url="https://github.com/org/repo",
            )


# ---------------------------------------------------------------------------
# CodingRealtimeClient (port 8694, env CODING_REALTIME_URL, timeout 10)
# ---------------------------------------------------------------------------


class TestCodingRealtimeClient:
    """Test CodingRealtimeClient URL resolution and methods."""

    def test_url_from_env(self):
        client = CodingRealtimeClient()
        assert client.base_url == "http://coding-realtime:8694"

    def test_raises_when_no_url_configured(self, monkeypatch):
        monkeypatch.delenv("CODING_REALTIME_URL", raising=False)
        with pytest.raises(RuntimeError, match="CODING_REALTIME_URL"):
            CodingRealtimeClient()

    def test_custom_url(self):
        client = CodingRealtimeClient(base_url="http://local:8888")
        assert client.base_url == "http://local:8888"

    def test_env_url(self):
        with patch.dict("os.environ", {"CODING_REALTIME_URL": "http://env-rt:9999"}):
            client = CodingRealtimeClient()
            assert client.base_url == "http://env-rt:9999"

    def test_default_timeout(self):
        client = CodingRealtimeClient()
        assert client.timeout == 10.0

    async def test_broadcast(self):
        client = CodingRealtimeClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"delivered": True, "subscriber_count": 5}
            result = await client.broadcast(
                event_type="container_started",
                data={"container_name": "c1", "status": "running"},
                priority="high",
                headers={"X-Tenant-Id": "t1"},
            )
            # Posts to the PUBLISH route (not the WS-only /subscribe), flat body.
            mock_post.assert_called_once_with(
                "/api/broadcast/publish",
                headers={"X-Tenant-Id": "t1"},
                json={
                    "event_type": "container_started",
                    "data": {"container_name": "c1", "status": "running"},
                    "priority": "high",
                },
            )
            assert result == {"delivered": True, "subscriber_count": 5}

    async def test_broadcast_includes_optional_fields_when_given(self):
        client = CodingRealtimeClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {}
            await client.broadcast(
                event_type="analysis_progress",
                data={},
                container_name="c2",
                tags=["python"],
                correlation_id="corr-1",
                ttl_seconds=30,
            )
            mock_post.assert_called_once_with(
                "/api/broadcast/publish",
                headers=None,
                json={
                    "event_type": "analysis_progress",
                    "data": {},
                    "priority": "normal",
                    "container_name": "c2",
                    "tags": ["python"],
                    "correlation_id": "corr-1",
                    "ttl_seconds": 30,
                },
            )


# ---------------------------------------------------------------------------
# CodingSecurityClient (port 8693, env CODING_SECURITY_URL, timeout 30)
# ---------------------------------------------------------------------------


class TestCodingSecurityClient:
    """Test CodingSecurityClient URL resolution and methods."""

    def test_url_from_env(self):
        client = CodingSecurityClient()
        assert client.base_url == "http://coding-security:8693"

    def test_raises_when_no_url_configured(self, monkeypatch):
        monkeypatch.delenv("CODING_SECURITY_URL", raising=False)
        with pytest.raises(RuntimeError, match="CODING_SECURITY_URL"):
            CodingSecurityClient()

    def test_custom_url(self):
        client = CodingSecurityClient(base_url="http://local:1234")
        assert client.base_url == "http://local:1234"

    def test_env_url(self):
        with patch.dict("os.environ", {"CODING_SECURITY_URL": "http://env-sec:5678"}):
            client = CodingSecurityClient()
            assert client.base_url == "http://env-sec:5678"

    async def test_scan(self):
        client = CodingSecurityClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"scan_id": "s1"}
            result = await client.scan("my-container", depth=3)
            mock_post.assert_called_once_with(
                "/api/security/scan/my-container",
                headers=None,
                json={"depth": 3},
            )
            assert result == {"scan_id": "s1"}

    async def test_get_scan_results(self):
        client = CodingSecurityClient()
        with patch.object(client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"vulnerabilities": []}
            result = await client.get_scan_results("my-container")
            mock_get.assert_called_once_with("/api/security/report/my-container", headers=None)
            assert result == {"vulnerabilities": []}

    async def test_analyze_vulnerabilities(self):
        client = CodingSecurityClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"findings": []}
            result = await client.analyze_vulnerabilities(
                file_paths=["src/app.py", "src/db.py"],
                max_files=10,
            )
            mock_post.assert_called_once_with(
                "/api/security/analyze-vulnerabilities",
                headers=None,
                json={"file_paths": ["src/app.py", "src/db.py"], "max_files": 10},
            )
            assert result == {"findings": []}

    async def test_analyze_vulnerabilities_default_max_files(self):
        client = CodingSecurityClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"findings": []}
            await client.analyze_vulnerabilities(file_paths=["a.py"])
            mock_post.assert_called_once_with(
                "/api/security/analyze-vulnerabilities",
                headers=None,
                json={"file_paths": ["a.py"], "max_files": 20},
            )

    async def test_analyze_vulnerabilities_with_extra_kwargs(self):
        client = CodingSecurityClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {}
            await client.analyze_vulnerabilities(
                file_paths=["a.py"],
                max_files=5,
                severity="high",
            )
            mock_post.assert_called_once_with(
                "/api/security/analyze-vulnerabilities",
                headers=None,
                json={"file_paths": ["a.py"], "max_files": 5, "severity": "high"},
            )


# ---------------------------------------------------------------------------
# CodingTestingClient (port 8689, env CODING_TESTING_URL, timeout 30)
# ---------------------------------------------------------------------------


class TestCodingTestingClient:
    """Test CodingTestingClient URL resolution and methods."""

    def test_url_from_env(self):
        client = CodingTestingClient()
        assert client.base_url == "http://coding-testing:8689"

    def test_raises_when_no_url_configured(self, monkeypatch):
        monkeypatch.delenv("CODING_TESTING_URL", raising=False)
        with pytest.raises(RuntimeError, match="CODING_TESTING_URL"):
            CodingTestingClient()

    def test_custom_url(self):
        client = CodingTestingClient(base_url="http://local:4321")
        assert client.base_url == "http://local:4321"

    def test_env_url(self):
        with patch.dict("os.environ", {"CODING_TESTING_URL": "http://env-test:6789"}):
            client = CodingTestingClient()
            assert client.base_url == "http://env-test:6789"

    async def test_run_tests(self):
        client = CodingTestingClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"test_id": "t1"}
            result = await client.run_tests(language="python", code="assert True")
            mock_post.assert_called_once_with(
                "/api/tests/execute",
                headers=None,
                json={"language": "python", "code": "assert True"},
            )
            assert result == {"test_id": "t1"}

    async def test_run_tests_with_headers(self):
        client = CodingTestingClient()
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"test_id": "t2"}
            headers = {"X-Tenant": "tenant-1"}
            result = await client.run_tests(headers=headers, language="go", code="func Test(){}")
            mock_post.assert_called_once_with(
                "/api/tests/execute",
                headers=headers,
                json={"language": "go", "code": "func Test(){}"},
            )
            assert result == {"test_id": "t2"}
