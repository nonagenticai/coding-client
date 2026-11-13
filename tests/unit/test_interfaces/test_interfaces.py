"""Tests for coding_client.interfaces — all ABC/Protocol contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from coding_client.interfaces.cache_interface import IAnalysisCache, ICacheManager
from coding_client.interfaces.container_interface import (
    ContainerInfo,
    IContainerManager,
)
from coding_client.interfaces.docker_interface import IDockerService
from coding_client.interfaces.graph_interface import IGraphService
from coding_client.interfaces.security_interface import ISecurityService
from coding_client.interfaces.webhook_interface import (
    IWebhookEventHandler,
    WebhookEventHandlerRegistry,
)


# ---------------------------------------------------------------------------
# IAnalysisCache
# ---------------------------------------------------------------------------
class TestIAnalysisCache:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            IAnalysisCache()

    def test_has_expected_abstract_methods(self):
        assert "get_cached_result" in IAnalysisCache.__abstractmethods__
        assert "cache_result" in IAnalysisCache.__abstractmethods__

    def test_concrete_subclass_can_be_instantiated(self):
        class Concrete(IAnalysisCache):
            async def get_cached_result(self, file_path: Path, content: str) -> Any | None:
                return None

            async def cache_result(self, file_path: Path, content: str, parse_result: Any) -> None:
                pass

        obj = Concrete()
        assert isinstance(obj, IAnalysisCache)


# ---------------------------------------------------------------------------
# ICacheManager
# ---------------------------------------------------------------------------
class TestICacheManager:
    EXPECTED_METHODS = {
        "get",
        "set",
        "delete",
        "delete_pattern",
        "get_or_compute",
        "get_stats",
        "clear_stats",
        "get_container_stats",
        "clear_container_cache",
        "get_container_keys",
        "close",
    }

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ICacheManager()

    def test_has_all_expected_abstract_methods(self):
        for method in self.EXPECTED_METHODS:
            assert method in ICacheManager.__abstractmethods__, f"Missing abstract method: {method}"

    def test_no_unexpected_abstract_methods(self):
        assert ICacheManager.__abstractmethods__ == frozenset(self.EXPECTED_METHODS)

    def test_concrete_subclass_can_be_instantiated(self):
        class Concrete(ICacheManager):
            async def get(self, key):
                return None

            async def set(self, key, value, ttl=None):
                return True

            async def delete(self, key, record_eviction=True, eviction_reason="manual"):
                return True

            async def delete_pattern(self, pattern):
                return 0

            async def get_or_compute(self, key, compute_func, ttl=None):
                return await compute_func()

            def get_stats(self):
                return {}

            async def clear_stats(self):
                pass

            async def get_container_stats(self, container_name):
                return {}

            async def clear_container_cache(self, container_name):
                return 0

            async def get_container_keys(self, container_name, limit=100, offset=0):
                return []

            async def close(self):
                pass

        obj = Concrete()
        assert isinstance(obj, ICacheManager)


# ---------------------------------------------------------------------------
# ContainerInfo (Protocol)
# ---------------------------------------------------------------------------
class TestContainerInfoProtocol:
    def test_object_satisfying_protocol(self):
        """An object with the right attributes satisfies the Protocol at runtime."""

        class Info:
            container_name: str = "my-container"
            code_graph_id: str = "graph-1"
            status: str = "running"
            api_endpoint: str | None = "http://localhost:9000"

        info = Info()
        # Runtime isinstance check only works if Protocol has runtime_checkable;
        # ContainerInfo is a plain Protocol, so we just verify attribute access.
        assert info.container_name == "my-container"
        assert info.code_graph_id == "graph-1"
        assert info.status == "running"
        assert info.api_endpoint == "http://localhost:9000"

    def test_protocol_defines_expected_attributes(self):
        annotations = ContainerInfo.__annotations__
        assert "container_name" in annotations
        assert "code_graph_id" in annotations
        assert "status" in annotations
        assert "api_endpoint" in annotations


# ---------------------------------------------------------------------------
# IContainerManager
# ---------------------------------------------------------------------------
class TestIContainerManager:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            IContainerManager()

    def test_has_expected_abstract_methods(self):
        assert "get_container_for_graph" in IContainerManager.__abstractmethods__
        assert "list_containers" in IContainerManager.__abstractmethods__

    def test_concrete_subclass_can_be_instantiated(self):
        class Concrete(IContainerManager):
            def get_container_for_graph(self, code_graph_id):
                return None

            def list_containers(self):
                return []

        obj = Concrete()
        assert isinstance(obj, IContainerManager)


# ---------------------------------------------------------------------------
# IDockerService
# ---------------------------------------------------------------------------
class TestIDockerService:
    EXPECTED_METHODS = {
        "is_docker_available",
        "retry_docker_connection",
        "create_container",
        "remove_container",
        "remove_container_by_name",
        "remove_container_by_id",
        "start_container",
        "stop_container",
        "list_containers",
        "find_container_by_name",
        "find_existing_container",
        "initialize_code_graph",
        "read_container_file",
        "list_container_directory",
        "exec_in_container",
        "create_file_in_container",
        "get_container_stats",
        "get_language_container_image",
        "create_test_container",
        "install_tools_in_container",
    }

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            IDockerService()

    def test_has_all_expected_abstract_methods(self):
        for method in self.EXPECTED_METHODS:
            assert method in IDockerService.__abstractmethods__, (
                f"Missing abstract method: {method}"
            )

    def test_no_unexpected_abstract_methods(self):
        assert IDockerService.__abstractmethods__ == frozenset(self.EXPECTED_METHODS)

    def test_concrete_subclass_can_be_instantiated(self):
        class Concrete(IDockerService):
            def is_docker_available(self):
                return True

            def retry_docker_connection(self):
                return True

            async def create_container(self, request, env_vars=None):
                return MagicMock()

            async def remove_container(self, container):
                return True

            async def remove_container_by_name(self, container_name):
                return True

            async def remove_container_by_id(self, docker_id, force=True):
                pass

            async def start_container(self, docker_id):
                pass

            async def stop_container(self, docker_id, timeout=10):
                pass

            async def list_containers(self):
                return []

            async def find_container_by_name(self, container_name):
                return None

            async def find_existing_container(self, repo_url):
                return None

            async def initialize_code_graph(self, container, analysis_settings=None):
                return container

            async def read_container_file(self, container_name, file_path, offset=0, length=None):
                return {}

            async def list_container_directory(self, container_name, path="", recursive=False):
                return []

            async def exec_in_container(
                self, docker_id, command, timeout=30, environment=None, user=None
            ):
                return {}

            async def create_file_in_container(self, docker_id, file_path, content, mode="w"):
                return True

            async def get_container_stats(self, docker_id):
                return {}

            def get_language_container_image(self, language):
                return "python:3.13"

            async def create_test_container(self, config):
                return "container-id"

            async def install_tools_in_container(self, docker_id, tools, language="python"):
                return True

        obj = Concrete()
        assert isinstance(obj, IDockerService)


# ---------------------------------------------------------------------------
# IGraphService
# ---------------------------------------------------------------------------
class TestIGraphService:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            IGraphService()

    def test_has_expected_abstract_methods(self):
        assert "delete_graph" in IGraphService.__abstractmethods__

    def test_concrete_subclass_can_be_instantiated(self):
        class Concrete(IGraphService):
            async def delete_graph(self, graph_id, force=False):
                return {"deleted": True}

        obj = Concrete()
        assert isinstance(obj, IGraphService)


# ---------------------------------------------------------------------------
# ISecurityService
# ---------------------------------------------------------------------------
class TestISecurityService:
    EXPECTED_METHODS = {
        "validate_code_security",
        "generate_sandbox_config",
        "get_dangerous_patterns",
        "get_sandbox_config",
    }

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ISecurityService()

    def test_has_all_expected_abstract_methods(self):
        for method in self.EXPECTED_METHODS:
            assert method in ISecurityService.__abstractmethods__, (
                f"Missing abstract method: {method}"
            )

    def test_no_unexpected_abstract_methods(self):
        assert ISecurityService.__abstractmethods__ == frozenset(self.EXPECTED_METHODS)

    def test_concrete_subclass_can_be_instantiated(self):
        class Concrete(ISecurityService):
            async def validate_code_security(self, request):
                return MagicMock()

            async def generate_sandbox_config(self, language, security_level):
                return {}

            def get_dangerous_patterns(self, language):
                return []

            def get_sandbox_config(self, language):
                return None

        obj = Concrete()
        assert isinstance(obj, ISecurityService)


# ---------------------------------------------------------------------------
# IWebhookEventHandler
# ---------------------------------------------------------------------------
class TestIWebhookEventHandler:
    EXPECTED_METHODS = {
        "analyze_pull_request_changes",
        "analyze_repository_changes",
    }

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            IWebhookEventHandler()

    def test_has_expected_abstract_methods(self):
        for method in self.EXPECTED_METHODS:
            assert method in IWebhookEventHandler.__abstractmethods__, (
                f"Missing abstract method: {method}"
            )

    def test_concrete_subclass_can_be_instantiated(self):
        class Concrete(IWebhookEventHandler):
            async def analyze_pull_request_changes(self, repo_name, pr_number, trigger):
                pass

            async def analyze_repository_changes(self, repo_name, branch, commits):
                return {}

        obj = Concrete()
        assert isinstance(obj, IWebhookEventHandler)


# ---------------------------------------------------------------------------
# WebhookEventHandlerRegistry
# ---------------------------------------------------------------------------
class TestWebhookEventHandlerRegistry:
    def setup_method(self):
        """Clear registry between tests to avoid cross-test pollution."""
        WebhookEventHandlerRegistry._handlers = {}

    def test_register_and_get_handler(self):
        handler = MagicMock(spec=IWebhookEventHandler)
        WebhookEventHandlerRegistry.register("test", handler)
        assert WebhookEventHandlerRegistry.get_handler("test") is handler

    def test_get_handler_returns_none_for_unknown(self):
        assert WebhookEventHandlerRegistry.get_handler("nonexistent") is None

    def test_get_raises_for_unknown(self):
        with pytest.raises(ValueError, match="No handler registered with name"):
            WebhookEventHandlerRegistry.get("nonexistent")

    def test_get_returns_registered_handler(self):
        handler = MagicMock(spec=IWebhookEventHandler)
        WebhookEventHandlerRegistry.register("myhandler", handler)
        assert WebhookEventHandlerRegistry.get("myhandler") is handler

    def test_register_overwrites_existing(self):
        h1 = MagicMock(spec=IWebhookEventHandler)
        h2 = MagicMock(spec=IWebhookEventHandler)
        WebhookEventHandlerRegistry.register("key", h1)
        WebhookEventHandlerRegistry.register("key", h2)
        assert WebhookEventHandlerRegistry.get("key") is h2


# ---------------------------------------------------------------------------
# __init__.py re-exports
# ---------------------------------------------------------------------------
class TestInterfacesInit:
    def test_all_exports_importable(self):
        from coding_client.interfaces import (
            IAnalysisCache,
            ICacheManager,
            IContainerInfo,
            IDockerService,
            IGraphService,
            ISecurityService,
            IWebhookEventHandler,
        )

        # Smoke-check that these are the real classes/protocols
        assert IAnalysisCache is not None
        assert ICacheManager is not None
        assert IContainerInfo is not None
        assert IDockerService is not None
        assert IGraphService is not None
        assert ISecurityService is not None
        assert IWebhookEventHandler is not None

    def test_icontainer_info_is_container_info_protocol(self):
        from coding_client.interfaces import IContainerInfo

        # __init__.py aliases ContainerInfo as IContainerInfo
        assert IContainerInfo is ContainerInfo
