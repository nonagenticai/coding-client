"""Tests for coding_client.models.responses module."""

from __future__ import annotations

from coding_client.models.responses import (
    COMMON_RESPONSES,
    BadRequestResponse,
    ForbiddenResponse,
    GoneResponse,
    InternalServerErrorResponse,
    LegacyBaseResponse,
    LegacyResponseStatus,
    LegacyStandardErrorResponse,
    NotFoundResponse,
    NotImplementedResponse,
    ServiceUnavailableResponse,
    SimpleValidationErrorResponse,
    TimeoutResponse,
    UnauthorizedResponse,
    ValidationErrorDetail,
    bad_request,
    conflict,
    error_response,
    forbidden,
    get_all_responses,
    get_auth_responses,
    get_common_responses,
    get_standard_responses,
    internal_error,
    not_found,
    rate_limited,
    service_unavailable,
    success_response,
    timeout_error,
    unauthorized,
    validation_error,
)
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# LegacyResponseStatus enum
# ---------------------------------------------------------------------------


class TestLegacyResponseStatus:
    """Tests for LegacyResponseStatus enum."""

    def test_success_value(self):
        assert LegacyResponseStatus.SUCCESS == "success"

    def test_error_value(self):
        assert LegacyResponseStatus.ERROR == "error"

    def test_warning_value(self):
        assert LegacyResponseStatus.WARNING == "warning"


# ---------------------------------------------------------------------------
# LegacyBaseResponse
# ---------------------------------------------------------------------------


class TestLegacyBaseResponse:
    """Tests for LegacyBaseResponse model."""

    def test_default_status(self):
        resp = LegacyBaseResponse()
        assert resp.status == LegacyResponseStatus.SUCCESS

    def test_custom_status(self):
        resp = LegacyBaseResponse(status=LegacyResponseStatus.ERROR, message="fail")
        assert resp.status == LegacyResponseStatus.ERROR
        assert resp.message == "fail"

    def test_with_data(self):
        resp = LegacyBaseResponse(data={"key": "value"})
        assert resp.data == {"key": "value"}

    def test_defaults_none(self):
        resp = LegacyBaseResponse()
        assert resp.message is None
        assert resp.data is None


# ---------------------------------------------------------------------------
# Error response models
# ---------------------------------------------------------------------------


class TestValidationErrorDetail:
    """Tests for ValidationErrorDetail."""

    def test_create(self):
        d = ValidationErrorDetail(loc=["body", "name"], msg="field required", type="missing")
        assert d.loc == ["body", "name"]
        assert d.msg == "field required"


class TestLegacyStandardErrorResponse:
    """Tests for LegacyStandardErrorResponse."""

    def test_create(self):
        r = LegacyStandardErrorResponse(detail="Something went wrong")
        assert r.detail == "Something went wrong"
        assert r.status_code is None
        assert r.type is None

    def test_with_status_code(self):
        r = LegacyStandardErrorResponse(detail="Bad", status_code=400, type="bad_request")
        assert r.status_code == 400


class TestSimpleValidationErrorResponse:
    """Tests for SimpleValidationErrorResponse."""

    def test_create(self):
        detail = ValidationErrorDetail(loc=["body"], msg="missing", type="value_error")
        r = SimpleValidationErrorResponse(detail=[detail])
        assert len(r.detail) == 1


class TestNotFoundResponse:
    def test_create(self):
        r = NotFoundResponse(detail="Not found")
        assert r.detail == "Not found"


class TestUnauthorizedResponse:
    def test_create(self):
        r = UnauthorizedResponse(detail="Unauthorized")
        assert r.detail == "Unauthorized"


class TestForbiddenResponse:
    def test_create(self):
        r = ForbiddenResponse(detail="Forbidden")
        assert r.detail == "Forbidden"


class TestInternalServerErrorResponse:
    def test_create(self):
        r = InternalServerErrorResponse(detail="Internal error")
        assert r.detail == "Internal error"


class TestBadRequestResponse:
    def test_defaults(self):
        r = BadRequestResponse(detail="Bad request")
        assert r.status_code == 400
        assert r.type == "input_validation_error"


class TestServiceUnavailableResponse:
    def test_create(self):
        r = ServiceUnavailableResponse(detail="Service down")
        assert r.detail == "Service down"


class TestGoneResponse:
    def test_create(self):
        r = GoneResponse(detail="Deprecated")
        assert r.detail == "Deprecated"


class TestNotImplementedResponse:
    def test_create(self):
        r = NotImplementedResponse(detail="Not implemented")
        assert r.detail == "Not implemented"


class TestTimeoutResponse:
    def test_create(self):
        r = TimeoutResponse(detail="Timeout")
        assert r.detail == "Timeout"


# ---------------------------------------------------------------------------
# success_response helper
# ---------------------------------------------------------------------------


class TestSuccessResponse:
    """Tests for success_response helper function."""

    def test_returns_dict_with_status_success(self):
        result = success_response({"items": [1, 2, 3]})
        assert result["status"] == "success"
        assert result["data"] == {"items": [1, 2, 3]}
        assert result["message"] == "Success"

    def test_custom_message(self):
        result = success_response("ok", message="All good")
        assert result["message"] == "All good"
        assert result["data"] == "ok"

    def test_none_data(self):
        result = success_response(None)
        assert result["data"] is None
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# error_response helper
# ---------------------------------------------------------------------------


class TestErrorResponse:
    """Tests for error_response helper function."""

    def test_returns_http_exception(self):
        exc = error_response(400, "Bad input")
        assert isinstance(exc, HTTPException)
        assert exc.status_code == 400
        assert exc.detail["status"] == "error"
        assert exc.detail["message"] == "Bad input"
        assert exc.detail["error_code"] == "INTERNAL_ERROR"

    def test_custom_error_code(self):
        exc = error_response(422, "Invalid", error_code="VALIDATION")
        assert exc.detail["error_code"] == "VALIDATION"

    def test_with_details(self):
        exc = error_response(500, "Fail", details={"key": "val"})
        assert exc.detail["details"] == {"key": "val"}


# ---------------------------------------------------------------------------
# Convenience error helpers
# ---------------------------------------------------------------------------


class TestNotFoundHelper:
    def test_creates_404(self):
        exc = not_found("User", "123")
        assert exc.status_code == 404
        assert "User" in exc.detail["message"]
        assert "123" in exc.detail["message"]
        assert exc.detail["error_code"] == "USER_NOT_FOUND"


class TestBadRequestHelper:
    def test_creates_400(self):
        exc = bad_request("Missing field")
        assert exc.status_code == 400
        assert exc.detail["error_code"] == "BAD_REQUEST"


class TestValidationErrorHelper:
    def test_creates_422(self):
        exc = validation_error("Invalid email", "email")
        assert exc.status_code == 422
        assert exc.detail["details"]["field"] == "email"


class TestInternalErrorHelper:
    def test_creates_500(self):
        exc = internal_error("Crash")
        assert exc.status_code == 500


class TestUnauthorizedHelper:
    def test_creates_401(self):
        exc = unauthorized()
        assert exc.status_code == 401

    def test_custom_message(self):
        exc = unauthorized("Token expired")
        assert exc.detail["message"] == "Token expired"


class TestForbiddenHelper:
    def test_creates_403(self):
        exc = forbidden()
        assert exc.status_code == 403


class TestConflictHelper:
    def test_creates_409(self):
        exc = conflict("Container", "Already exists")
        assert exc.status_code == 409
        assert exc.detail["error_code"] == "CONTAINER_CONFLICT"


class TestServiceUnavailableHelper:
    def test_creates_503(self):
        exc = service_unavailable()
        assert exc.status_code == 503


class TestTimeoutErrorHelper:
    def test_creates_504(self):
        exc = timeout_error()
        assert exc.status_code == 504


class TestRateLimitedHelper:
    def test_creates_429(self):
        exc = rate_limited()
        assert exc.status_code == 429


# ---------------------------------------------------------------------------
# get_common_responses / get_standard_responses / get_auth_responses
# ---------------------------------------------------------------------------


class TestResponseSchemaHelpers:
    """Tests for response schema helper functions."""

    def test_get_common_responses_subset(self):
        result = get_common_responses(400, 404)
        assert 400 in result
        assert 404 in result
        assert 500 not in result

    def test_get_common_responses_unknown_code_ignored(self):
        result = get_common_responses(999)
        assert result == {}

    def test_get_standard_responses(self):
        result = get_standard_responses()
        assert 400 in result
        assert 404 in result
        assert 422 in result
        assert 500 in result

    def test_get_auth_responses(self):
        result = get_auth_responses()
        assert 401 in result
        assert 403 in result
        assert 400 not in result

    def test_get_all_responses(self):
        result = get_all_responses()
        assert set(result.keys()) == set(COMMON_RESPONSES.keys())

    def test_all_responses_is_copy(self):
        result = get_all_responses()
        result[999] = {"description": "custom"}
        assert 999 not in COMMON_RESPONSES
