"""Request validation middleware for coding-* services.

Provides URL normalisation, control-character detection, and structured
error responses. Shared across services so each consumer can mount the
middleware via a thin re-export rather than maintaining its own copy.
"""

from __future__ import annotations

import logging
import re
import traceback
import uuid
from urllib.parse import unquote

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class SecurityValidationException(HTTPException):
    """HTTPException subclass for security validation failures."""

    def __init__(
        self,
        status_code: int = 400,
        detail: str = "Security validation failed",
        is_security_error: bool = True,
        error_code: str = "SECURITY_VALIDATION_ERROR",
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.is_security_error = is_security_error
        self.error_code = error_code


# Paths excluded from deep validation (health checks, etc.)
_EXCLUDE_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/healthz",
        "/ready",
        "/readyz",
        "/",
    }
)

# Regex for dangerous control characters (NULL, 0x01-0x08, VT, FF, 0x0E-0x1F, DEL)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ValidationMiddleware(BaseHTTPMiddleware):
    """Pre-processes and validates incoming requests."""

    def __init__(self, app, exclude_paths: frozenset[str] | None = None, **kwargs):
        super().__init__(app, **kwargs)
        self._exclude_paths = exclude_paths or _EXCLUDE_PATHS

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Skip validation for excluded paths
        if path in self._exclude_paths:
            return await call_next(request)

        try:
            # Normalise URL path
            normalised = self._preprocess_request(path)
            if normalised != path:
                request.scope["path"] = normalised

            # Check for dangerous control characters in URL
            self._validate_request_security(request)

            return await call_next(request)

        except SecurityValidationException as exc:
            return self._create_validation_error_response(exc)

        except HTTPException as exc:
            return self._create_http_error_response(exc)

        except Exception as exc:
            logger.error("Unexpected validation error: %s", exc, exc_info=True)
            return self._create_system_error_response(exc)

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _preprocess_request(path: str) -> str:
        """Normalise the URL path (collapse slashes, decode, strip trailing slash)."""
        path = re.sub(r"/+", "/", path)
        try:
            path = unquote(path)
        except Exception:
            logger.debug("URL unquote failed for path")
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")
        return path

    def _validate_request_security(self, request: Request) -> None:
        """Reject requests with dangerous control characters in the URL."""
        raw_url = str(request.url)
        if _CONTROL_CHAR_RE.search(raw_url):
            raise SecurityValidationException(
                status_code=400,
                detail="Request contains invalid control characters",
                error_code="CONTROL_CHAR_DETECTED",
            )

    @staticmethod
    def _create_validation_error_response(exc: SecurityValidationException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "error_code": exc.error_code,
                "status_code": exc.status_code,
            },
        )

    @staticmethod
    def _create_http_error_response(exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": str(exc.detail),
                "status_code": exc.status_code,
            },
        )

    @staticmethod
    def _create_system_error_response(exc: Exception) -> JSONResponse:
        request_id = str(uuid.uuid4())
        logger.error(
            "System error [%s]: %s\n%s",
            request_id,
            exc,
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "error_code": "INTERNAL_ERROR",
                "request_id": request_id,
                "status_code": 500,
            },
        )
