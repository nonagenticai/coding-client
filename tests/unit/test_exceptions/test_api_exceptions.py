"""Tests for coding_client.exceptions.api_exceptions."""

from __future__ import annotations

from coding_client.exceptions.api_exceptions import (
    AgentConfigurationError,
    AITimeoutError,
    AIValidationError,
    AuthenticationException,
    BaseAPIException,
    ConflictException,
    ContainerNotFoundException,
    InternalServerException,
    NotFoundException,
    PermissionException,
    ProcessingException,
    RateLimitException,
    ServiceUnavailableException,
    ValidationException,
)
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# BaseAPIException
# ---------------------------------------------------------------------------


class TestBaseAPIException:
    def test_inherits_http_exception(self):
        assert issubclass(BaseAPIException, HTTPException)

    def test_basic_construction(self):
        exc = BaseAPIException(
            status_code=400,
            message="bad request",
            error_code="BAD",
        )
        assert exc.status_code == 400
        assert exc.error_code == "BAD"
        assert exc.detail["message"] == "bad request"
        assert exc.detail["error_code"] == "BAD"

    def test_with_details(self):
        exc = BaseAPIException(
            status_code=500,
            message="fail",
            error_code="FAIL",
            details={"extra": "info"},
        )
        assert exc.detail["details"] == {"extra": "info"}
        assert exc.details == {"extra": "info"}
        assert exc.error_details == {"extra": "info"}

    def test_without_details(self):
        exc = BaseAPIException(status_code=200, message="ok", error_code="OK")
        assert "details" not in exc.detail
        assert exc.details is None

    def test_with_headers(self):
        exc = BaseAPIException(
            status_code=401,
            message="unauth",
            error_code="UNAUTH",
            headers={"X-Custom": "val"},
        )
        assert exc.headers == {"X-Custom": "val"}


# ---------------------------------------------------------------------------
# AgentConfigurationError
# ---------------------------------------------------------------------------


class TestAgentConfigurationError:
    def test_defaults(self):
        exc = AgentConfigurationError()
        assert exc.status_code == 400
        assert exc.error_code == "AGENT_CONFIG_ERROR"
        assert exc.detail["message"] == "Agent configuration error"

    def test_custom_message(self):
        exc = AgentConfigurationError(message="bad agent config")
        assert exc.detail["message"] == "bad agent config"

    def test_with_details(self):
        exc = AgentConfigurationError(details={"field": "model_name"})
        assert exc.detail["details"]["field"] == "model_name"


# ---------------------------------------------------------------------------
# AITimeoutError
# ---------------------------------------------------------------------------


class TestAITimeoutError:
    def test_defaults(self):
        exc = AITimeoutError()
        assert exc.status_code == 504
        assert exc.error_code == "AI_TIMEOUT"
        assert exc.detail["message"] == "AI service timeout"

    def test_custom(self):
        exc = AITimeoutError(message="model timed out", details={"timeout_ms": 30000})
        assert exc.detail["message"] == "model timed out"
        assert exc.detail["details"]["timeout_ms"] == 30000


# ---------------------------------------------------------------------------
# AIValidationError
# ---------------------------------------------------------------------------


class TestAIValidationError:
    def test_defaults(self):
        exc = AIValidationError()
        assert exc.status_code == 422
        assert exc.error_code == "AI_VALIDATION_ERROR"

    def test_custom(self):
        exc = AIValidationError(message="invalid prompt")
        assert exc.detail["message"] == "invalid prompt"


# ---------------------------------------------------------------------------
# NotFoundException
# ---------------------------------------------------------------------------


class TestNotFoundException:
    def test_defaults(self):
        exc = NotFoundException()
        assert exc.status_code == 404
        assert exc.error_code == "NOT_FOUND"

    def test_with_resource_type_and_id(self):
        exc = NotFoundException(resource_type="container", resource_id="abc-123")
        assert exc.detail["details"]["resource_type"] == "container"
        assert exc.detail["details"]["resource_id"] == "abc-123"

    def test_with_resource_type_only(self):
        exc = NotFoundException(resource_type="user")
        assert exc.detail["details"]["resource_type"] == "user"

    def test_with_existing_details(self):
        exc = NotFoundException(
            resource_type="file",
            details={"path": "/tmp/missing"},
        )
        assert exc.detail["details"]["resource_type"] == "file"
        assert exc.detail["details"]["path"] == "/tmp/missing"


# ---------------------------------------------------------------------------
# ValidationException
# ---------------------------------------------------------------------------


class TestValidationException:
    def test_defaults(self):
        exc = ValidationException()
        assert exc.status_code == 400
        assert exc.error_code == "VALIDATION_FAILED"

    def test_with_field(self):
        exc = ValidationException(field="email")
        assert exc.detail["details"]["field"] == "email"

    def test_custom_message(self):
        exc = ValidationException(message="Name too long", field="name")
        assert exc.detail["message"] == "Name too long"
        assert exc.detail["details"]["field"] == "name"


# ---------------------------------------------------------------------------
# AuthenticationException
# ---------------------------------------------------------------------------


class TestAuthenticationException:
    def test_defaults(self):
        exc = AuthenticationException()
        assert exc.status_code == 401
        assert exc.error_code == "UNAUTHORIZED"

    def test_www_authenticate_header_auto_added(self):
        exc = AuthenticationException()
        assert exc.headers["WWW-Authenticate"] == "Bearer"

    def test_custom_headers_preserved(self):
        exc = AuthenticationException(headers={"X-Custom": "val"})
        assert exc.headers["WWW-Authenticate"] == "Bearer"
        assert exc.headers["X-Custom"] == "val"

    def test_custom_www_authenticate_not_overwritten(self):
        exc = AuthenticationException(headers={"WWW-Authenticate": "Basic"})
        assert exc.headers["WWW-Authenticate"] == "Basic"


# ---------------------------------------------------------------------------
# PermissionException
# ---------------------------------------------------------------------------


class TestPermissionException:
    def test_defaults(self):
        exc = PermissionException()
        assert exc.status_code == 403
        assert exc.error_code == "FORBIDDEN"

    def test_with_required_permission(self):
        exc = PermissionException(required_permission="admin:write")
        assert exc.detail["details"]["required_permission"] == "admin:write"


# ---------------------------------------------------------------------------
# ConflictException
# ---------------------------------------------------------------------------


class TestConflictException:
    def test_defaults(self):
        exc = ConflictException()
        assert exc.status_code == 409
        assert exc.error_code == "CONFLICT"

    def test_with_conflicting_resource(self):
        exc = ConflictException(conflicting_resource="container-xyz")
        assert exc.detail["details"]["conflicting_resource"] == "container-xyz"


# ---------------------------------------------------------------------------
# ServiceUnavailableException
# ---------------------------------------------------------------------------


class TestServiceUnavailableException:
    def test_defaults(self):
        exc = ServiceUnavailableException()
        assert exc.status_code == 503
        assert exc.error_code == "SERVICE_UNAVAILABLE"

    def test_with_retry_after(self):
        exc = ServiceUnavailableException(retry_after=30)
        assert exc.headers["Retry-After"] == "30"
        assert exc.detail["details"]["retry_after_seconds"] == 30

    def test_without_retry_after(self):
        exc = ServiceUnavailableException()
        assert exc.headers is None or "Retry-After" not in (exc.headers or {})


# ---------------------------------------------------------------------------
# RateLimitException
# ---------------------------------------------------------------------------


class TestRateLimitException:
    def test_defaults(self):
        exc = RateLimitException()
        assert exc.status_code == 429
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"

    def test_all_rate_limit_headers(self):
        exc = RateLimitException(
            retry_after=60,
            limit=100,
            remaining=0,
            reset=1700000000,
        )
        assert exc.headers["Retry-After"] == "60"
        assert exc.headers["X-RateLimit-Limit"] == "100"
        assert exc.headers["X-RateLimit-Remaining"] == "0"
        assert exc.headers["X-RateLimit-Reset"] == "1700000000"

    def test_rate_limit_in_details(self):
        exc = RateLimitException(limit=100, remaining=5, reset=9999)
        assert exc.detail["details"]["limit"] == 100
        assert exc.detail["details"]["remaining"] == 5
        assert exc.detail["details"]["reset"] == 9999

    def test_partial_headers(self):
        exc = RateLimitException(limit=50)
        assert exc.headers["X-RateLimit-Limit"] == "50"
        assert "Retry-After" not in exc.headers


# ---------------------------------------------------------------------------
# ProcessingException
# ---------------------------------------------------------------------------


class TestProcessingException:
    def test_defaults(self):
        exc = ProcessingException()
        assert exc.status_code == 422
        assert exc.error_code == "UNPROCESSABLE_ENTITY"

    def test_with_reason(self):
        exc = ProcessingException(reason="corrupt data")
        assert exc.detail["details"]["reason"] == "corrupt data"


# ---------------------------------------------------------------------------
# InternalServerException
# ---------------------------------------------------------------------------


class TestInternalServerException:
    def test_defaults(self):
        exc = InternalServerException()
        assert exc.status_code == 500
        assert exc.error_code == "INTERNAL_ERROR"

    def test_custom(self):
        exc = InternalServerException(message="db crashed", details={"db": "main"})
        assert exc.detail["message"] == "db crashed"
        assert exc.detail["details"]["db"] == "main"


# ---------------------------------------------------------------------------
# ContainerNotFoundException
# ---------------------------------------------------------------------------


class TestContainerNotFoundException:
    def test_defaults(self):
        exc = ContainerNotFoundException(container_name="my-app")
        assert exc.status_code == 400
        assert exc.error_code == "CONTAINER_NOT_FOUND"
        assert "my-app" in exc.detail["message"]

    def test_details_contain_resource_info(self):
        exc = ContainerNotFoundException(container_name="test-container")
        details = exc.detail["details"]
        assert details["resource_type"] == "container"
        assert details["resource_id"] == "test-container"

    def test_custom_message(self):
        exc = ContainerNotFoundException(container_name="x", message="custom msg")
        assert exc.detail["message"] == "custom msg"

    def test_existing_details_merged(self):
        exc = ContainerNotFoundException(
            container_name="c1",
            details={"extra": "data"},
        )
        assert exc.detail["details"]["extra"] == "data"
        assert exc.detail["details"]["resource_type"] == "container"
