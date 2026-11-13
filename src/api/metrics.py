"""Request timing middleware for coding-* services.

Measures request duration, sets an ``X-Process-Time`` header, and emits a
structured ``request_complete`` log line for downstream aggregation. Uses
structured-log timing rather than Prometheus counters; an OpenTelemetry
metrics SDK can be wired in here if counter/histogram exports are needed.
"""

from __future__ import annotations

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

logger = logging.getLogger(__name__)


async def add_process_time_header(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """Measure request duration and add ``X-Process-Time`` header."""
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{duration:.4f}"

    # Structured log for downstream aggregation
    logger.info(
        "request_complete",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": getattr(response, "status_code", 0),
            "duration_s": round(duration, 4),
        },
    )
    return response
