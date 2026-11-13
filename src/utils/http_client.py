"""Unified HTTP client wrapper with retry logic, error handling, and timeout management.

This module provides a standardized HTTP client that handles common patterns like
retries, timeouts, error handling, and logging across the application.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from functools import wraps
from typing import Any
from urllib.parse import urljoin

import httpx as requests  # httpx as drop-in replacement for requests (CVE-2026-25645)

# Shims for requests API compatibility
HTTPAdapter = None
Retry = None

try:
    import aiohttp  # noqa: F401 — used by ``from aiohttp import`` below

    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

if HAS_AIOHTTP:
    from aiohttp import ClientError, ClientSession, ClientTimeout
else:
    ClientTimeout = None
    ClientSession = None
    ClientError = None

logger = logging.getLogger(__name__)


class HTTPClientError(Exception):
    """Base exception for HTTP client errors."""

    pass


class HTTPTimeoutError(HTTPClientError):
    """Raised when an HTTP request times out."""

    pass


class HTTPConnectionError(HTTPClientError):
    """Raised when connection to server fails."""

    pass


class HTTPResponseError(HTTPClientError):
    """Raised when server returns an error response."""

    def __init__(self, message: str, status_code: int, response_text: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        total: int = 3,
        backoff_factor: float = 0.3,
        status_forcelist: list[int] | None = None,
        method_whitelist: list[str] | None = None,
    ):
        self.total = total
        self.backoff_factor = backoff_factor
        self.status_forcelist = status_forcelist or [429, 500, 502, 503, 504]
        self.method_whitelist = method_whitelist or [
            "GET",
            "PUT",
            "DELETE",
            "OPTIONS",
            "TRACE",
            "HEAD",
        ]


class HTTPClient:
    """Unified HTTP client with retry logic and error handling."""

    DEFAULT_TIMEOUT = 30.0
    DEFAULT_RETRY_CONFIG = RetryConfig()

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_config: RetryConfig | None = None,
        headers: dict[str, str] | None = None,
    ):
        """Initialize HTTP client.

        Args:
            base_url: Optional base URL for all requests
            timeout: Default timeout in seconds
            retry_config: Retry configuration
            headers: Default headers to include in all requests
        """
        self.base_url = base_url
        self.timeout = timeout
        self.retry_config = retry_config or self.DEFAULT_RETRY_CONFIG
        self.default_headers = headers or {}

        # Setup sync session with retry adapter
        self._sync_session = self._create_sync_session()

        # Async session will be created on demand
        self._async_session: ClientSession | None = None

    def _create_sync_session(self) -> requests.Client:
        """Create an httpx client with timeout configuration."""
        transport = requests.HTTPTransport(retries=self.retry_config.total)
        session = requests.Client(
            transport=transport,
            timeout=self.timeout,
        )

        # Set default headers
        session.headers.update(self.default_headers)

        return session

    async def _ensure_async_session(self) -> ClientSession:
        """Ensure async session is created."""
        if not HAS_AIOHTTP:
            raise ImportError("aiohttp module not available - install with 'pip install aiohttp'")

        if self._async_session is None or self._async_session.closed:
            assert ClientTimeout is not None, "aiohttp must be installed"
            assert ClientSession is not None, "aiohttp must be installed"
            timeout = ClientTimeout(total=self.timeout)
            self._async_session = ClientSession(
                timeout=timeout,
                headers=self.default_headers,
            )
        return self._async_session

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        if self.base_url:
            return urljoin(self.base_url, endpoint)
        return endpoint

    def _log_request(self, method: str, url: str, **kwargs):
        """Log HTTP request details."""
        logger.debug(
            f"HTTP {method} {url}",
            extra={
                "http_method": method,
                "http_url": url,
                "http_params": kwargs.get("params"),
                "http_headers": kwargs.get("headers"),
            },
        )

    def _log_response(self, method: str, url: str, status_code: int, duration: float):
        """Log HTTP response details."""
        logger.debug(
            f"HTTP {method} {url} - {status_code} ({duration:.2f}s)",
            extra={
                "http_method": method,
                "http_url": url,
                "http_status_code": status_code,
                "http_duration": duration,
            },
        )

    def _handle_response_error(self, response: requests.Response | Any, method: str, url: str):
        """Handle HTTP error responses."""
        status_code: int = (
            response.status_code if hasattr(response, "status_code") else response.status
        )

        if 400 <= status_code < 500:
            error_msg = f"Client error on {method} {url}: {status_code}"
            response_text = ""
            try:
                if hasattr(response, "text"):
                    response_text = response.text
                else:
                    # For async response, we'd need to await response.text()
                    # This is handled in the async methods
                    pass
            except Exception:
                pass

            logger.error(
                error_msg,
                extra={
                    "http_status_code": status_code,
                    "http_response": response_text[:500] if response_text else "",
                },
            )
            raise HTTPResponseError(error_msg, status_code, response_text)

        elif status_code >= 500:
            error_msg = f"Server error on {method} {url}: {status_code}"
            logger.error(error_msg, extra={"http_status_code": status_code})
            raise HTTPResponseError(error_msg, status_code)

    # Synchronous methods

    def get(self, endpoint: str, **kwargs) -> requests.Response:
        """Perform GET request."""
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs) -> requests.Response:
        """Perform POST request."""
        return self.request("POST", endpoint, **kwargs)

    def put(self, endpoint: str, **kwargs) -> requests.Response:
        """Perform PUT request."""
        return self.request("PUT", endpoint, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        """Perform DELETE request."""
        return self.request("DELETE", endpoint, **kwargs)

    def patch(self, endpoint: str, **kwargs) -> requests.Response:
        """Perform PATCH request."""
        return self.request("PATCH", endpoint, **kwargs)

    def request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Perform synchronous HTTP request with error handling.

        Args:
            method: HTTP method
            endpoint: URL endpoint
            **kwargs: Additional arguments passed to requests

        Returns:
            Response object

        Raises:
            HTTPTimeoutError: On timeout
            HTTPConnectionError: On connection failure
            HTTPResponseError: On error response
        """
        url = self._build_url(endpoint)

        # Set default timeout if not provided
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout

        # Merge headers
        if "headers" in kwargs:
            headers = {**self.default_headers, **kwargs["headers"]}
            kwargs["headers"] = headers

        self._log_request(method, url, **kwargs)
        start_time = time.time()

        try:
            response = self._sync_session.request(method, url, **kwargs)
            duration = time.time() - start_time
            self._log_response(method, url, response.status_code, duration)

            # Check for HTTP errors
            response.raise_for_status()

            return response

        except requests.TimeoutException as e:
            logger.error(f"Timeout on {method} {url}: {e}")
            raise HTTPTimeoutError(f"Request timeout on {method} {url}") from e

        except requests.ConnectError as e:
            logger.error(f"Connection error on {method} {url}: {e}")
            raise HTTPConnectionError(f"Connection failed on {method} {url}") from e

        except requests.HTTPStatusError as e:
            # Handle error responses
            if e.response is not None:
                self._handle_response_error(e.response, method, url)
            raise

        except Exception as e:
            logger.error(f"Unexpected error on {method} {url}: {e}")
            raise HTTPClientError(f"Unexpected error on {method} {url}: {e}") from e

    # Asynchronous methods

    async def async_get(self, endpoint: str, **kwargs) -> Any:
        """Perform async GET request."""
        return await self.async_request("GET", endpoint, **kwargs)

    async def async_post(self, endpoint: str, **kwargs) -> Any:
        """Perform async POST request."""
        return await self.async_request("POST", endpoint, **kwargs)

    async def async_put(self, endpoint: str, **kwargs) -> Any:
        """Perform async PUT request."""
        return await self.async_request("PUT", endpoint, **kwargs)

    async def async_delete(self, endpoint: str, **kwargs) -> Any:
        """Perform async DELETE request."""
        return await self.async_request("DELETE", endpoint, **kwargs)

    async def async_patch(self, endpoint: str, **kwargs) -> Any:
        """Perform async PATCH request."""
        return await self.async_request("PATCH", endpoint, **kwargs)

    async def async_request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Perform asynchronous HTTP request with error handling and retries.

        Args:
            method: HTTP method
            endpoint: URL endpoint
            **kwargs: Additional arguments passed to aiohttp

        Returns:
            Response data as dictionary

        Raises:
            HTTPTimeoutError: On timeout
            HTTPConnectionError: On connection failure
            HTTPResponseError: On error response
        """
        url = self._build_url(endpoint)
        session = await self._ensure_async_session()
        assert session is not None, "HTTP session must be available"

        # Merge headers
        headers = {**self.default_headers}
        if "headers" in kwargs:
            headers.update(kwargs["headers"])
            kwargs["headers"] = headers
        else:
            kwargs["headers"] = headers

        self._log_request(method, url, **kwargs)

        # Implement retry logic
        last_exception = None
        for attempt in range(self.retry_config.total + 1):
            if attempt > 0:
                # Exponential backoff
                sleep_time = self.retry_config.backoff_factor * (2 ** (attempt - 1))
                logger.debug(f"Retrying {method} {url} after {sleep_time}s (attempt {attempt + 1})")
                await asyncio.sleep(sleep_time)

            start_time = time.time()

            try:
                async with session.request(method, url, **kwargs) as response:
                    duration = time.time() - start_time
                    self._log_response(method, url, response.status, duration)

                    # Check status code
                    if response.status >= 400:
                        response_text = await response.text()
                        if (
                            response.status in self.retry_config.status_forcelist
                            and attempt < self.retry_config.total
                        ):
                            # Retry on specific status codes
                            last_exception = HTTPResponseError(
                                f"Server error on {method} {url}: {response.status}",
                                response.status,
                                response_text,
                            )
                            continue

                        # Non-retryable error
                        error_msg = f"{'Client' if response.status < 500 else 'Server'} error on {method} {url}: {response.status}"
                        logger.error(
                            error_msg,
                            extra={
                                "http_status_code": response.status,
                                "http_response": (response_text[:500] if response_text else ""),
                            },
                        )
                        raise HTTPResponseError(error_msg, response.status, response_text)

                    # Success - return response data
                    try:
                        return await response.json()
                    except Exception:
                        # If JSON parsing fails, return text
                        text = await response.text()
                        return {"text": text, "status": response.status}

            except TimeoutError as e:
                logger.error(f"Timeout on {method} {url}: {e}")
                last_exception = HTTPTimeoutError(f"Request timeout on {method} {url}")

            except Exception as e:
                if HAS_AIOHTTP and ClientError and isinstance(e, ClientError):
                    logger.error(f"Client error on {method} {url}: {e}")
                    last_exception = HTTPConnectionError(
                        f"Connection failed on {method} {url}: {e}"
                    )
                else:
                    logger.error(f"Unexpected error on {method} {url}: {e}")
                    last_exception = HTTPClientError(f"Unexpected error on {method} {url}: {e}")

        # All retries failed
        if last_exception:
            raise last_exception
        else:
            raise HTTPClientError(
                f"Failed to complete request after {self.retry_config.total + 1} attempts"
            )

    def close(self):
        """Close all sessions.

        For async sessions, attempts to close properly by detecting the event loop.
        For guaranteed async cleanup, use aclose() instead from async context.
        """
        self._sync_session.close()
        if self._async_session:
            try:
                # Try to get running loop and schedule proper cleanup
                loop = asyncio.get_running_loop()
                # Schedule cleanup task - will be awaited by event loop
                loop.create_task(self._async_session.close())
            except RuntimeError:
                # No running loop - try synchronous close via new loop
                try:
                    asyncio.run(self._async_session.close())
                except RuntimeError:
                    # Loop already running in another thread or closed
                    # Last resort: mark session as needing cleanup
                    logger.warning(
                        "Could not properly close async session - prefer using aclose() from async context"
                    )

    async def aclose(self):
        """Async close all sessions."""
        self._sync_session.close()
        if self._async_session:
            await self._async_session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.aclose()


# Convenience functions for one-off requests


def get(url: str, **kwargs) -> requests.Response:
    """Perform one-off GET request with default retry logic."""
    with HTTPClient() as client:
        return client.get(url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    """Perform one-off POST request with default retry logic."""
    with HTTPClient() as client:
        return client.post(url, **kwargs)


async def async_get(url: str, **kwargs) -> dict[str, Any]:
    """Perform one-off async GET request with default retry logic."""
    async with HTTPClient() as client:
        return await client.async_get(url, **kwargs)


async def async_post(url: str, **kwargs) -> dict[str, Any]:
    """Perform one-off async POST request with default retry logic."""
    async with HTTPClient() as client:
        return await client.async_post(url, **kwargs)


# Decorator for automatic retry on specific functions


def with_http_retry(
    retries: int = 3,
    backoff_factor: float = 0.3,
    exceptions: tuple = (HTTPTimeoutError, HTTPConnectionError),
):
    """Decorator to add retry logic to functions making HTTP calls.

    Args:
        retries: Number of retry attempts
        backoff_factor: Backoff multiplier between retries
        exceptions: Tuple of exceptions to retry on
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(retries + 1):
                if attempt > 0:
                    sleep_time = backoff_factor * (2 ** (attempt - 1))
                    logger.debug(
                        f"Retrying {func.__name__} after {sleep_time}s (attempt {attempt + 1})"
                    )
                    time.sleep(sleep_time)

                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    logger.warning(f"Retry-able error in {func.__name__}: {e}")
                    last_exception = e
                except Exception:
                    # Non-retryable exception
                    raise

            # All retries exhausted
            if last_exception:
                raise last_exception

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(retries + 1):
                if attempt > 0:
                    sleep_time = backoff_factor * (2 ** (attempt - 1))
                    logger.debug(
                        f"Retrying {func.__name__} after {sleep_time}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(sleep_time)

                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    logger.warning(f"Retry-able error in {func.__name__}: {e}")
                    last_exception = e
                except Exception:
                    # Non-retryable exception
                    raise

            # All retries exhausted
            if last_exception:
                raise last_exception

        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator
