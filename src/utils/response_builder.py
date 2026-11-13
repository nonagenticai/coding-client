"""Standardized response utilities for the refactored API.

This module provides utilities for creating consistent response formats across
all API endpoints. It includes:

- StandardResponse: Pydantic model for standardized API responses
- ResponseBuilder: Builder class for creating success and error responses
- Convenience functions for quick response creation

The response format includes:
- success: Boolean indicating success/failure
- data: The actual response data
- meta: Metadata including execution time, source, and timestamp
- links: Optional related links for API navigation
- error: Error details when applicable

Usage:
    builder = ResponseBuilder(request)
    return builder.success(data, source="container")

    # Or use convenience functions
    return build_success_response(data, request=request)
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from pydantic import BaseModel


class StandardResponse(BaseModel):
    """Standard response format for all API endpoints.

    Attributes:
        success: Boolean indicating whether the request was successful
        data: The actual response data (can be dict, list, or primitive types)
        meta: Metadata including execution time, source, and timestamp
        links: Optional related links for API navigation
        error: Error details when request fails (mutually exclusive with data)
    """

    success: bool
    data: dict[str, Any] | list[Any] | str | int | bool | None = None
    meta: dict[str, Any]
    links: dict[str, str] | None = None
    error: dict[str, Any] | None = None


class ResponseBuilder:
    """Builder for creating standardized responses.

    Provides methods to build consistent success and error responses with
    automatic metadata generation including execution time and timestamps.

    Attributes:
        request: Optional FastAPI request object for context
        start_time: Timestamp when builder was created (for execution time calculation)
    """

    def __init__(self, request: Request | None = None):
        """
        Initialize the response builder.

        Args:
            request: Optional FastAPI request object for generating contextual links
        """
        self.request = request
        self.start_time = time.time()

    def success(
        self,
        data: Any,
        source: str = "local",
        container_name: str | None = None,
        additional_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Build a success response with standardized metadata.

        Args:
            data: The response data to include
            source: Source of the data (e.g., "local", "container", "cached")
            container_name: Optional name of the container that processed the request
            additional_meta: Optional additional metadata to include

        Returns:
            Dictionary containing standardized success response
        """

        execution_time = int((time.time() - self.start_time) * 1000)

        meta = {
            "source": source,
            "execution_time_ms": execution_time,
            "api_version": "v2",
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if container_name:
            meta["container_name"] = container_name

        if additional_meta:
            meta.update(additional_meta)

        response = {"success": True, "data": data, "meta": meta}

        # Add links if request context is available
        if self.request:
            response["links"] = self._build_links()

        return response

    def error(
        self,
        error_message: str,
        error_code: str | None = None,
        suggestions: list[str] | None = None,
        available_endpoints: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Build an error response with actionable guidance.

        Args:
            error_message: Human-readable error message
            error_code: Optional error code for programmatic handling
            suggestions: Optional list of suggestions to resolve the error
            available_endpoints: Optional list of available endpoints for guidance

        Returns:
            Dictionary containing standardized error response
        """

        execution_time = int((time.time() - self.start_time) * 1000)

        error_data: dict[str, Any] = {
            "message": error_message,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if error_code:
            error_data["code"] = error_code

        if suggestions:
            error_data["suggestions"] = suggestions

        if available_endpoints:
            error_data["available_endpoints"] = available_endpoints

        return {
            "success": False,
            "data": None,
            "meta": {
                "execution_time_ms": execution_time,
                "api_version": "v2",
                "timestamp": datetime.now(UTC).isoformat(),
            },
            "error": error_data,
        }

    def _build_links(self) -> dict[str, str]:
        """
        Build related links based on the current request.

        Generates contextual links for API navigation based on the request path.

        Returns:
            Dictionary of related links for the current endpoint
        """
        if not self.request:
            return {}

        base_url = f"{self.request.url.scheme}://{self.request.url.netloc}"
        path = str(self.request.url.path)

        links = {"sel": f"{base_url}{path}"}

        # Add contextual links based on the path
        if "/graphs/" in path:
            graph_id = path.split("/graphs/")[1].split("/")[0]
            links.update(
                {
                    "graph_details": f"{base_url}/api/v2/graphs/{graph_id}",
                    "graph_nodes": f"{base_url}/api/v2/graphs/{graph_id}/nodes",
                    "all_graphs": f"{base_url}/api/v2/graphs/",
                }
            )
        elif "/containers/" in path:
            links["all_containers"] = f"{base_url}/api/v2/containers/"

        return links


def build_success_response(
    data: Any,
    source: str = "local",
    container_name: str | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    """
    Convenience function to build success responses.

    Args:
        data: The response data to include
        source: Source of the data (e.g., "local", "container", "cached")
        container_name: Optional name of the container that processed the request
        request: Optional FastAPI request object for generating contextual links

    Returns:
        Dictionary containing standardized success response
    """
    builder = ResponseBuilder(request)
    return builder.success(data, source, container_name)


def build_error_response(
    error_message: str,
    error_code: str | None = None,
    suggestions: list[str] | None = None,
    available_endpoints: list[str] | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    """
    Convenience function to build error responses.

    Args:
        error_message: Human-readable error message
        error_code: Optional error code for programmatic handling
        suggestions: Optional list of suggestions to resolve the error
        available_endpoints: Optional list of available endpoints for guidance
        request: Optional FastAPI request object for generating contextual links

    Returns:
        Dictionary containing standardized error response
    """
    builder = ResponseBuilder(request)
    return builder.error(error_message, error_code, suggestions, available_endpoints)
