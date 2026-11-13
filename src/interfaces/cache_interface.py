"""
Cache interface for breaking circular dependencies.

This module provides abstract interfaces for cache operations to prevent
circular dependencies between analysis_cache and language processing modules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # TODO: service-specific import removed
    # from ..processing.languages.base import ParseResult
    pass


class IAnalysisCache(ABC):
    """Abstract interface for analysis cache operations."""

    @abstractmethod
    async def get_cached_result(self, file_path: Path, content: str) -> Any | None:
        """Get cached analysis result if available and valid.

        Args:
            file_path: Path to the source file
            content: Current file content

        Returns:
            Cached ParseResult if available, None otherwise
        """
        pass

    @abstractmethod
    async def cache_result(self, file_path: Path, content: str, parse_result: Any) -> None:
        """Cache an analysis result.

        Args:
            file_path: Path to the source file
            content: File content that was analyzed
            parse_result: Analysis result to cache
        """
        pass


class ICacheManager(ABC):
    """Abstract interface for Redis-based cache manager operations."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds

        Returns:
            True if successful, False otherwise
        """
        ...

    @abstractmethod
    async def delete(
        self, key: str, record_eviction: bool = True, eviction_reason: str = "manual"
    ) -> bool:
        """Delete a value from cache.

        Args:
            key: Cache key
            record_eviction: Whether to record this deletion as an eviction
            eviction_reason: Reason for eviction

        Returns:
            True if successful, False otherwise
        """
        ...

    @abstractmethod
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching a pattern.

        Args:
            pattern: Key pattern (e.g., "container:*")

        Returns:
            Number of keys deleted
        """
        ...

    @abstractmethod
    async def get_or_compute(
        self, key: str, compute_func: Callable[[], Any], ttl: int | None = None
    ) -> Any:
        """Get from cache or compute and cache.

        Args:
            key: Cache key
            compute_func: Function to compute value if not cached
            ttl: Time-to-live in seconds

        Returns:
            Cached or computed value
        """
        ...

    @abstractmethod
    def get_stats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with hits, misses, errors counts
        """
        ...

    @abstractmethod
    async def clear_stats(self) -> None:
        """Reset cache statistics."""
        ...

    @abstractmethod
    async def get_container_stats(self, container_name: str) -> dict[str, Any]:
        """Get cache statistics for a specific container.

        Args:
            container_name: Name of the container to get stats for

        Returns:
            Dictionary with hit_count, miss_count, size, entry_count
        """
        ...

    @abstractmethod
    async def clear_container_cache(self, container_name: str) -> int:
        """Clear all cache entries for a specific container.

        Args:
            container_name: Name of the container whose cache should be cleared

        Returns:
            Number of cache entries deleted
        """
        ...

    @abstractmethod
    async def get_container_keys(
        self, container_name: str, limit: int = 100, offset: int = 0
    ) -> list[str]:
        """Get paginated list of cache keys for a specific container.

        Args:
            container_name: Name of the container to get keys for
            limit: Maximum number of keys to return
            offset: Number of keys to skip

        Returns:
            List of cache key strings
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the cache manager and clean up resources."""
        ...
