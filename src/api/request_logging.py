"""Request Logging Middleware (KAG standard).

Generates unique request IDs, logs request start/end with timing,
and adds X-Request-ID + X-Processing-Time response headers.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_SKIP_LOG_PATHS = frozenset({"/health", "/healthz", "/ready", "/readyz"})


class HealthCheckFilter(logging.Filter):
    """Filter out health check requests from uvicorn access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "/health" not in record.getMessage()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log requests and add tracking headers (KAG standard)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in _SKIP_LOG_PATHS:
            return await call_next(request)

        request_id: str = str(uuid.uuid4())
        request.state.request_id = request_id

        start_time: float = time.time()

        logger.info("Request started: %s %s [%s]", request.method, request.url.path, request_id)

        response: Response = await call_next(request)

        process_time: float = (time.time() - start_time) * 1000

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Processing-Time"] = f"{process_time:.2f}ms"

        logger.info(
            "Request completed: %s %s [%s] - Status: %s - Time: %.2fms",
            request.method,
            request.url.path,
            request_id,
            response.status_code,
            process_time,
        )

        return response
