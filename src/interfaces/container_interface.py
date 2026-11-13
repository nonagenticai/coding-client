"""
Container interface for breaking circular dependencies.

This module provides abstract interfaces for container operations to prevent
circular dependencies between container_manager and graph_service modules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol


class ContainerInfo(Protocol):
    """Protocol for container information objects."""

    container_name: str
    code_graph_id: str
    status: str
    api_endpoint: str | None


class IContainerManager(ABC):
    """Abstract interface for container management operations."""

    @abstractmethod
    def get_container_for_graph(self, code_graph_id: str) -> ContainerInfo | None:
        """Get container information for a specific code graph ID.

        Args:
            code_graph_id: The code graph identifier

        Returns:
            ContainerInfo if found, None otherwise
        """
        pass

    @abstractmethod
    def list_containers(self) -> list[ContainerInfo]:
        """List all containers.

        Returns:
            List of ContainerInfo objects
        """
        pass


# Type alias for container manager instances
ContainerManagerType = IContainerManager
