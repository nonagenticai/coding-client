"""Base async HTTP client with retry, error handling, and structured logging."""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)


class ServiceError(Exception):
    """Raised when a downstream service returns a non-2xx response."""

    def __init__(self, status_code: int, message: str, body: Any = None):
        self.status_code = status_code
        self.body = body
        super().__init__(message)


class ServiceClient:
    """Base async HTTP client for inter-service communication."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        *,
        max_attempts: int | None = None,
        **kwargs: Any,
    ) -> Any:
        """Send one request, retrying transport errors up to ``max_retries`` attempts.

        ``max_attempts`` overrides ``max_retries`` for this call only. Pass ``1``
        for a non-idempotent POST (e.g. a job submit), where a retry after a
        read timeout would start the work a second time.
        """
        client = await self._ensure_client()
        attempts = self.max_retries if max_attempts is None else max_attempts
        log = logger.bind(method=method, path=path, base_url=self.base_url)

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=1, min=0.5, max=10),
            retry=retry_if_exception_type(
                (httpx.ConnectError, httpx.ReadTimeout, httpx.PoolTimeout)
            ),
            reraise=True,
        ):
            with attempt:
                log.debug("http_request", attempt=attempt.retry_state.attempt_number)
                response = await client.request(method, path, headers=headers, **kwargs)

        if response.status_code >= 400:
            body = None
            try:
                body = response.json()
            except Exception:
                body = response.text
            msg = f"{method} {self.base_url}{path} returned {response.status_code}"
            log.error("service_error", status_code=response.status_code, body=body)
            raise ServiceError(response.status_code, msg, body=body)

        if response.status_code == 204 or not response.content:
            return None

        try:
            return response.json()
        except Exception:
            return response.text

    async def get(self, path: str, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        return await self._request("GET", path, headers=headers, **kwargs)

    async def post(self, path: str, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        return await self._request("POST", path, headers=headers, **kwargs)

    async def put(self, path: str, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        return await self._request("PUT", path, headers=headers, **kwargs)

    async def delete(self, path: str, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        return await self._request("DELETE", path, headers=headers, **kwargs)

    async def patch(self, path: str, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        return await self._request("PATCH", path, headers=headers, **kwargs)

    async def health_check(self) -> bool:
        try:
            await self.get("/health")
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> ServiceClient:
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
