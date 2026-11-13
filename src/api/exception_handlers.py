"""KAG-standard exception handlers.

Produces the nested ``{error: {code, message, timestamp, request_id, details}}``
response envelope used across all KAG and coding-* services.
"""

from __future__ import annotations

import logging
import time
import traceback
import uuid
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


def _get_request_id(request: Request) -> str:
    """Get request_id from state (set by RequestLoggingMiddleware) or generate one."""
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _error_response(
    status_code: int,
    *,
    code: str,
    message: str,
    request_id: str,
    details: object = None,
    headers: dict[str, str] | Mapping[str, str] | None = None,
) -> JSONResponse:
    body: dict = {
        "code": code,
        "message": message,
        "timestamp": _timestamp(),
        "request_id": request_id,
    }
    if details is not None:
        body["details"] = details
    return JSONResponse(
        status_code=status_code,
        content={"error": body},
        headers=headers,
    )


def register_exception_handlers(app: FastAPI, *, debug: bool = False) -> None:
    """Register KAG-standard exception handlers on *app*."""

    async def _handle_http(request: Request, exc: Exception) -> JSONResponse:
        http_exc = exc if isinstance(exc, HTTPException) else HTTPException(status_code=500)
        request_id = _get_request_id(request)
        if isinstance(http_exc.detail, dict):
            message = http_exc.detail.get("message", str(http_exc.detail))
        else:
            message = str(http_exc.detail)
        return _error_response(
            http_exc.status_code,
            code=f"HTTP_{http_exc.status_code}",
            message=message,
            request_id=request_id,
            details=http_exc.detail.get("details") if isinstance(http_exc.detail, dict) else None,
            headers=http_exc.headers if hasattr(http_exc, "headers") else None,
        )

    app.add_exception_handler(HTTPException, _handle_http)

    @app.exception_handler(Exception)
    async def _global(request: Request, exc: Exception) -> JSONResponse:
        request_id = _get_request_id(request)

        # HTTPException (includes BaseAPIException subclasses)
        if isinstance(exc, HTTPException):
            # Extract message from structured detail dicts
            if isinstance(exc.detail, dict):
                message = exc.detail.get("message", str(exc.detail))
            else:
                message = str(exc.detail)

            return _error_response(
                exc.status_code,
                code=f"HTTP_{exc.status_code}",
                message=message,
                request_id=request_id,
                details=exc.detail.get("details") if isinstance(exc.detail, dict) else None,
                headers=exc.headers if hasattr(exc, "headers") else None,
            )

        # BaseExceptionGroup wrapping HTTPException (Python 3.11+ TaskGroups)
        if isinstance(exc, BaseExceptionGroup):
            for sub_exc in exc.exceptions:
                if isinstance(sub_exc, HTTPException):
                    if isinstance(sub_exc.detail, dict):
                        message = sub_exc.detail.get("message", str(sub_exc.detail))
                    else:
                        message = str(sub_exc.detail)
                    return _error_response(
                        sub_exc.status_code,
                        code=f"HTTP_{sub_exc.status_code}",
                        message=message,
                        request_id=request_id,
                        headers=sub_exc.headers if hasattr(sub_exc, "headers") else None,
                    )
                if isinstance(sub_exc, BaseExceptionGroup):
                    for nested in sub_exc.exceptions:
                        if isinstance(nested, HTTPException):
                            msg = str(nested.detail)
                            return _error_response(
                                nested.status_code,
                                code=f"HTTP_{nested.status_code}",
                                message=msg,
                                request_id=request_id,
                                headers=nested.headers if hasattr(nested, "headers") else None,
                            )

        # Unhandled exception
        logger.error(
            "Unhandled exception [%s]: %s\n%s",
            request_id,
            exc,
            traceback.format_exc(),
        )
        return _error_response(
            500,
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
            request_id=request_id,
            details=str(exc) if debug else None,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = _get_request_id(request)
        validation_errors = [
            {
                "field": ".".join(str(loc) for loc in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
                "input": err.get("input"),
            }
            for err in exc.errors()
        ]
        return _error_response(
            422,
            code="HTTP_422",
            message="Request validation failed",
            request_id=request_id,
            details=validation_errors,
        )
