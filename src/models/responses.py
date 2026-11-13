"""Common response models for consistent API endpoint responses.

This module provides standardized response models that ensure consistency across all
API endpoints in the code graph helper system. These models support proper OpenAPI
documentation generation and provide a unified error handling experience.

The response models follow REST API best practices with:
- Consistent status codes and error formats
- Standardized field naming and structure
- Comprehensive OpenAPI documentation examples
- Type-safe response validation

Key Components:
    Base Models: BaseResponse, LegacyStandardErrorResponse for consistent structure
    Error Models: Specialized models for different HTTP error types (400, 401, 403, etc.)
    Utility Functions: Helper functions for generating response schemas
    Response Schemas: Pre-configured OpenAPI documentation examples

Example:
    ```python
    from common_responses_models import LegacyBaseResponse, LegacyResponseStatus, get_common_responses

    # Create a successful response
    response = LegacyBaseResponse(
        status=LegacyResponseStatus.SUCCESS,
        message="Operation completed successfully",
        data={"result": "value"}
    )

    # Get OpenAPI response schemas
    responses = get_common_responses(400, 404, 500)
    ```
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, Field


class LegacyResponseStatus(StrEnum):
    """Legacy response status enum (deprecated - use V2 API ResponseStatus)."""

    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"


class LegacyBaseResponse(BaseModel):
    """Legacy base response model (deprecated - use V2 API BaseResponse)."""

    status: LegacyResponseStatus = Field(
        default=LegacyResponseStatus.SUCCESS, description="Response status"
    )
    message: str | None = Field(default=None, description="Response message")
    data: dict[str, Any] | None = Field(default=None, description="Response data")


class ValidationErrorDetail(BaseModel):
    """Individual validation error detail."""

    loc: list[str] = Field(..., description="Location of the validation error")
    msg: str = Field(..., description="Error message")
    type: str = Field(..., description="Error type")


class LegacyStandardErrorResponse(BaseModel):
    """Legacy standard error response format (deprecated - use V2 API error models)."""

    detail: str = Field(..., description="Error message")
    status_code: int | None = Field(None, description="HTTP status code")
    type: str | None = Field(None, description="Error type")


class SimpleValidationErrorResponse(BaseModel):
    """Response model for validation errors (422)."""

    detail: list[ValidationErrorDetail] = Field(..., description="List of validation errors")


class NotFoundResponse(BaseModel):
    """Response model for resource not found errors (404)."""

    detail: str = Field(..., description="Resource not found message")


class UnauthorizedResponse(BaseModel):
    """Response model for authentication errors (401)."""

    detail: str = Field(..., description="Authentication error message")


class ForbiddenResponse(BaseModel):
    """Response model for authorization errors (403)."""

    detail: str = Field(..., description="Authorization error message")


class InternalServerErrorResponse(BaseModel):
    """Response model for server errors (500)."""

    detail: str = Field(..., description="Internal server error message")


class BadRequestResponse(BaseModel):
    """Response model for bad request errors (400)."""

    detail: str = Field(..., description="Bad request error message")
    status_code: int | None = Field(400, description="HTTP status code")
    type: str | None = Field("input_validation_error", description="Error type")


class ServiceUnavailableResponse(BaseModel):
    """Response model for service unavailable errors (503)."""

    detail: str = Field(..., description="Service unavailable error message")


class GoneResponse(BaseModel):
    """Response model for gone/deprecated resource errors (410)."""

    detail: str = Field(..., description="Resource is gone or deprecated message")


class NotImplementedResponse(BaseModel):
    """Response model for not implemented errors (501)."""

    detail: str = Field(..., description="Feature not implemented error message")


class TimeoutResponse(BaseModel):
    """Response model for timeout errors (408)."""

    detail: str = Field(..., description="Request timeout error message")


# Common response schemas for OpenAPI documentation
COMMON_RESPONSES = {
    400: {
        "description": "Bad Request - Invalid input or malformed request",
        "model": BadRequestResponse,
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Input validation error",
                        "value": {
                            "detail": "Invalid request body: Unsafe string contains illegal characters",
                            "status_code": 400,
                            "type": "input_validation_error",
                        },
                    },
                    "path_error": {
                        "summary": "Path validation error",
                        "value": {
                            "detail": "Invalid request path contains illegal characters",
                            "status_code": 400,
                            "type": "input_validation_error",
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication required or invalid credentials",
        "model": UnauthorizedResponse,
        "content": {
            "application/json": {"example": {"detail": "Invalid authentication credentials"}}
        },
    },
    403: {
        "description": "Forbidden - Insufficient permissions",
        "model": ForbiddenResponse,
        "content": {
            "application/json": {
                "example": {"detail": "Insufficient permissions to access this resource"}
            }
        },
    },
    404: {
        "description": "Not Found - Resource does not exist",
        "model": NotFoundResponse,
        "content": {"application/json": {"example": {"detail": "Resource not found"}}},
    },
    408: {
        "description": "Request Timeout - Request took too long to process",
        "model": TimeoutResponse,
        "content": {
            "application/json": {
                "example": {"detail": "Request timeout - processing took too long"}
            }
        },
    },
    410: {
        "description": "Gone - Resource is deprecated or no longer available",
        "model": GoneResponse,
        "content": {
            "application/json": {
                "example": {
                    "detail": "This endpoint has been deprecated. Use containerized alternatives."
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation errors",
        "model": SimpleValidationErrorResponse,
        "content": {
            "application/json": {
                "example": {
                    "detail": [
                        {
                            "loc": ["body", "field_name"],
                            "msg": "field required",
                            "type": "value_error.missing",
                        }
                    ]
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error - Unexpected server error",
        "model": InternalServerErrorResponse,
        "content": {"application/json": {"example": {"detail": "Internal server error occurred"}}},
    },
    501: {
        "description": "Not Implemented - Feature not yet implemented",
        "model": NotImplementedResponse,
        "content": {
            "application/json": {
                "example": {
                    "detail": "This feature is not yet implemented. Planned for future release."
                }
            }
        },
    },
    503: {
        "description": "Service Unavailable - External service is unavailable",
        "model": ServiceUnavailableResponse,
        "content": {
            "application/json": {"example": {"detail": "External service is currently unavailable"}}
        },
    },
}


def get_common_responses(*status_codes: int) -> dict[int, dict[str, Any]]:
    """Get common response schemas for specified status codes.

    Args:
        *status_codes: HTTP status codes to include

    Returns:
        Dict mapping status codes to response schemas
    """
    return {code: COMMON_RESPONSES[code] for code in status_codes if code in COMMON_RESPONSES}


def get_standard_responses() -> dict[int, dict[str, Any]]:
    """Get standard responses that most endpoints should include.

    Returns:
        Dict with common 400, 404, 422, and 500 responses
    """
    return get_common_responses(400, 404, 422, 500)


def get_auth_responses() -> dict[int, dict[str, Any]]:
    """Get authentication-related responses.

    Returns:
        Dict with 401 and 403 responses
    """
    return get_common_responses(401, 403)


def get_all_responses() -> dict[int, dict[str, Any]]:
    """Get all common response schemas.

    Returns:
        Dict with all defined response schemas
    """
    return COMMON_RESPONSES.copy()


# ============================================================================
# Response helper functions
# ============================================================================


def success_response(data: Any, message: str = "Success") -> dict:
    """Create a standardized success response.

    Args:
        data: The response data payload
        message: Optional success message

    Returns:
        Dict with standardized success format
    """
    return {
        "status": "success",
        "message": message,
        "data": data,
    }


def error_response(
    status_code: int,
    message: str,
    error_code: str = "INTERNAL_ERROR",
    details: dict | None = None,
) -> HTTPException:
    """Create a standardized error HTTPException.

    Args:
        status_code: HTTP status code
        message: Human-readable error message
        error_code: Machine-readable error code
        details: Additional error details

    Returns:
        HTTPException with standardized error format
    """
    return HTTPException(
        status_code=status_code,
        detail={
            "status": "error",
            "message": message,
            "error_code": error_code,
            "details": details or {},
        },
    )


def not_found(resource: str, identifier: str) -> HTTPException:
    """Create a 404 Not Found error."""
    return error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        message=f"{resource} '{identifier}' not found",
        error_code=f"{resource.upper().replace(' ', '_')}_NOT_FOUND",
    )


def bad_request(message: str, details: dict | None = None) -> HTTPException:
    """Create a 400 Bad Request error."""
    return error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        message=message,
        error_code="BAD_REQUEST",
        details=details,
    )


def validation_error(message: str, field: str, details: dict | None = None) -> HTTPException:
    """Create a 422 Validation Error."""
    return error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        message=message,
        error_code="VALIDATION_ERROR",
        details={"field": field, **(details or {})},
    )


def internal_error(message: str, details: dict | None = None) -> HTTPException:
    """Create a 500 Internal Server Error."""
    return error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message=message,
        error_code="INTERNAL_ERROR",
        details=details,
    )


def unauthorized(message: str = "Authentication required") -> HTTPException:
    """Create a 401 Unauthorized error."""
    return error_response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        message=message,
        error_code="UNAUTHORIZED",
    )


def forbidden(message: str = "Access denied") -> HTTPException:
    """Create a 403 Forbidden error."""
    return error_response(
        status_code=status.HTTP_403_FORBIDDEN,
        message=message,
        error_code="FORBIDDEN",
    )


def conflict(resource: str, message: str) -> HTTPException:
    """Create a 409 Conflict error."""
    return error_response(
        status_code=status.HTTP_409_CONFLICT,
        message=message,
        error_code=f"{resource.upper().replace(' ', '_')}_CONFLICT",
    )


def service_unavailable(message: str = "Service temporarily unavailable") -> HTTPException:
    """Create a 503 Service Unavailable error."""
    return error_response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        message=message,
        error_code="SERVICE_UNAVAILABLE",
    )


def timeout_error(message: str = "Request timed out") -> HTTPException:
    """Create a 504 Gateway Timeout error."""
    return error_response(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        message=message,
        error_code="TIMEOUT",
    )


def rate_limited(message: str = "Rate limit exceeded") -> HTTPException:
    """Create a 429 Too Many Requests error."""
    return error_response(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        message=message,
        error_code="RATE_LIMITED",
    )
