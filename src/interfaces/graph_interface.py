"""
Graph interface for breaking circular dependencies.

This module provides abstract interfaces for graph operations to prevent
circular dependencies between graph_service and container_manager modules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IGraphService(ABC):
    """Abstract interface for graph service operations."""

    @abstractmethod
    async def delete_graph(self, graph_id: str, force: bool = False) -> dict[str, Any]:
        """Delete a graph and all associated data.

        Args:
            graph_id: Unique identifier of the graph to delete
            force: If True, force deletion even for containerized graphs

        Returns:
            Dict containing deletion results
        """
        pass
