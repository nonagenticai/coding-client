"""Tests for coding_client.exceptions.pydantic_ai_exceptions."""

from __future__ import annotations

from coding_client.exceptions.pydantic_ai_exceptions import (
    AgentConfigurationError,
    AITimeoutError,
    AIValidationError,
    AnalysisError,
    APIKeyError,
    ModelNotFoundError,
    ModelProviderError,
    NonRetryableError,
    PydanticAIException,
    RateLimitError,
    ResourceExhaustedError,
    RetryableError,
    TokenLimitError,
    categorize_error,
    create_error_response,
    get_retry_delay,
    is_retryable_error,
)

# ---------------------------------------------------------------------------
# PydanticAIException (base)
# ---------------------------------------------------------------------------


class TestPydanticAIException:
    def test_message(self):
        exc = PydanticAIException("something broke")
        assert exc.message == "something broke"

    def test_error_code(self):
        exc = PydanticAIException("err", error_code="E001")
        assert exc.error_code == "E001"

    def test_details_default_empty(self):
        exc = PydanticAIException("err")
        assert exc.details == {}

    def test_details_set(self):
        exc = PydanticAIException("err", details={"k": "v"})
        assert exc.details == {"k": "v"}

    def test_cause(self):
        cause = RuntimeError("root")
        exc = PydanticAIException("wrapper", cause=cause)
        assert exc.cause is cause

    def test_str_message_only(self):
        exc = PydanticAIException("simple")
        assert str(exc) == "simple"

    def test_str_with_error_code(self):
        exc = PydanticAIException("msg", error_code="X")
        assert "Error code: X" in str(exc)

    def test_str_with_details(self):
        exc = PydanticAIException("msg", details={"a": 1})
        assert "Details:" in str(exc)

    def test_str_with_cause(self):
        exc = PydanticAIException("msg", cause=ValueError("inner"))
        assert "Caused by:" in str(exc)

    def test_to_dict(self):
        exc = PydanticAIException("msg", error_code="C", details={"x": 1})
        d = exc.to_dict()
        assert d["type"] == "PydanticAIException"
        assert d["message"] == "msg"
        assert d["error_code"] == "C"
        assert d["details"] == {"x": 1}
        assert d["cause"] is None

    def test_to_dict_with_cause(self):
        exc = PydanticAIException("msg", cause=ValueError("boom"))
        d = exc.to_dict()
        assert "boom" in d["cause"]

    def test_is_exception(self):
        assert issubclass(PydanticAIException, Exception)


# ---------------------------------------------------------------------------
# AgentConfigurationError
# ---------------------------------------------------------------------------


class TestAgentConfigurationError:
    def test_basic(self):
        exc = AgentConfigurationError("bad config")
        assert exc.message == "bad config"

    def test_agent_id_in_details(self):
        exc = AgentConfigurationError("err", agent_id="agent-1")
        assert exc.agent_id == "agent-1"
        assert exc.details["agent_id"] == "agent-1"

    def test_config_field_in_details(self):
        exc = AgentConfigurationError("err", config_field="model_name")
        assert exc.config_field == "model_name"
        assert exc.details["config_field"] == "model_name"

    def test_inherits_pydantic_ai(self):
        assert issubclass(AgentConfigurationError, PydanticAIException)


# ---------------------------------------------------------------------------
# ModelProviderError
# ---------------------------------------------------------------------------


class TestModelProviderError:
    def test_basic(self):
        exc = ModelProviderError("provider error")
        assert exc.message == "provider error"

    def test_provider_in_details(self):
        exc = ModelProviderError("err", provider="openai")
        assert exc.provider == "openai"
        assert exc.details["provider"] == "openai"

    def test_model_in_details(self):
        exc = ModelProviderError("err", model="gpt-4")
        assert exc.model == "gpt-4"
        assert exc.details["model"] == "gpt-4"

    def test_status_code_in_details(self):
        exc = ModelProviderError("err", status_code=500)
        assert exc.status_code == 500
        assert exc.details["status_code"] == 500


# ---------------------------------------------------------------------------
# APIKeyError
# ---------------------------------------------------------------------------


class TestAPIKeyError:
    def test_error_code(self):
        exc = APIKeyError("missing key")
        assert exc.error_code == "API_KEY_ERROR"

    def test_inherits_model_provider(self):
        assert issubclass(APIKeyError, ModelProviderError)

    def test_provider(self):
        exc = APIKeyError("bad key", provider="anthropic")
        assert exc.provider == "anthropic"


# ---------------------------------------------------------------------------
# RateLimitError
# ---------------------------------------------------------------------------


class TestRateLimitError:
    def test_error_code(self):
        exc = RateLimitError("rate limited")
        assert exc.error_code == "RATE_LIMIT"

    def test_retry_after(self):
        exc = RateLimitError("rate limited", retry_after=30)
        assert exc.retry_after == 30
        assert exc.details["retry_after"] == 30

    def test_inherits_model_provider(self):
        assert issubclass(RateLimitError, ModelProviderError)


# ---------------------------------------------------------------------------
# ModelNotFoundError
# ---------------------------------------------------------------------------


class TestModelNotFoundError:
    def test_error_code(self):
        exc = ModelNotFoundError("not found")
        assert exc.error_code == "MODEL_NOT_FOUND"

    def test_model_and_provider(self):
        exc = ModelNotFoundError("nf", provider="openai", model="gpt-5")
        assert exc.provider == "openai"
        assert exc.model == "gpt-5"


# ---------------------------------------------------------------------------
# TokenLimitError
# ---------------------------------------------------------------------------


class TestTokenLimitError:
    def test_error_code(self):
        exc = TokenLimitError("too many tokens")
        assert exc.error_code == "TOKEN_LIMIT"

    def test_token_count_and_limit(self):
        exc = TokenLimitError("limit", token_count=5000, token_limit=4096)
        assert exc.token_count == 5000
        assert exc.token_limit == 4096
        assert exc.details["token_count"] == 5000
        assert exc.details["token_limit"] == 4096


# ---------------------------------------------------------------------------
# AnalysisError
# ---------------------------------------------------------------------------


class TestAnalysisError:
    def test_basic(self):
        exc = AnalysisError("analysis failed")
        assert exc.message == "analysis failed"

    def test_analysis_type(self):
        exc = AnalysisError("err", analysis_type="security")
        assert exc.analysis_type == "security"
        assert exc.details["analysis_type"] == "security"

    def test_test_id(self):
        exc = AnalysisError("err", test_id="test-42")
        assert exc.test_id == "test-42"
        assert exc.details["test_id"] == "test-42"


# ---------------------------------------------------------------------------
# AIValidationError
# ---------------------------------------------------------------------------


class TestAIValidationError:
    def test_error_code(self):
        exc = AIValidationError("invalid input")
        assert exc.error_code == "VALIDATION_ERROR"

    def test_field_name_and_value(self):
        exc = AIValidationError("bad", field_name="prompt", field_value=123)
        assert exc.field_name == "prompt"
        assert exc.field_value == 123
        assert exc.details["field_name"] == "prompt"
        assert exc.details["field_value"] == "123"


# ---------------------------------------------------------------------------
# AITimeoutError
# ---------------------------------------------------------------------------


class TestAITimeoutError:
    def test_error_code(self):
        exc = AITimeoutError("timed out")
        assert exc.error_code == "TIMEOUT"

    def test_timeout_seconds(self):
        exc = AITimeoutError("timed out", timeout_seconds=30.0)
        assert exc.timeout_seconds == 30.0
        assert exc.details["timeout_seconds"] == 30.0

    def test_operation(self):
        exc = AITimeoutError("timed out", operation="inference")
        assert exc.operation == "inference"
        assert exc.details["operation"] == "inference"


# ---------------------------------------------------------------------------
# ResourceExhaustedError
# ---------------------------------------------------------------------------


class TestResourceExhaustedError:
    def test_error_code(self):
        exc = ResourceExhaustedError("no memory")
        assert exc.error_code == "RESOURCE_EXHAUSTED"

    def test_resource_type(self):
        exc = ResourceExhaustedError("no mem", resource_type="memory")
        assert exc.resource_type == "memory"
        assert exc.details["resource_type"] == "memory"


# ---------------------------------------------------------------------------
# RetryableError
# ---------------------------------------------------------------------------


class TestRetryableError:
    def test_error_code(self):
        exc = RetryableError("transient")
        assert exc.error_code == "RETRYABLE"

    def test_can_retry_true(self):
        exc = RetryableError("transient", retry_count=0, max_retries=3)
        assert exc.can_retry() is True

    def test_can_retry_false(self):
        exc = RetryableError("transient", retry_count=3, max_retries=3)
        assert exc.can_retry() is False

    def test_increment_retry(self):
        exc = RetryableError("transient", retry_count=0, max_retries=3)
        exc.increment_retry()
        assert exc.retry_count == 1
        assert exc.details["retry_count"] == 1

    def test_increment_until_exhausted(self):
        exc = RetryableError("transient", retry_count=0, max_retries=2)
        assert exc.can_retry() is True
        exc.increment_retry()
        assert exc.can_retry() is True
        exc.increment_retry()
        assert exc.can_retry() is False

    def test_details_contain_retry_info(self):
        exc = RetryableError("transient", retry_count=1, max_retries=5)
        assert exc.details["retry_count"] == 1
        assert exc.details["max_retries"] == 5


# ---------------------------------------------------------------------------
# NonRetryableError
# ---------------------------------------------------------------------------


class TestNonRetryableError:
    def test_error_code(self):
        exc = NonRetryableError("permanent")
        assert exc.error_code == "NON_RETRYABLE"

    def test_inherits_pydantic_ai(self):
        assert issubclass(NonRetryableError, PydanticAIException)


# ---------------------------------------------------------------------------
# is_retryable_error()
# ---------------------------------------------------------------------------


class TestIsRetryableError:
    def test_retryable_error_can_retry(self):
        err = RetryableError("err", retry_count=0, max_retries=3)
        assert is_retryable_error(err) is True

    def test_retryable_error_exhausted(self):
        err = RetryableError("err", retry_count=3, max_retries=3)
        assert is_retryable_error(err) is False

    def test_rate_limit_error(self):
        err = RateLimitError("rate limited")
        assert is_retryable_error(err) is True

    def test_non_retryable_error(self):
        err = NonRetryableError("permanent")
        assert is_retryable_error(err) is False

    def test_api_key_error(self):
        err = APIKeyError("bad key")
        assert is_retryable_error(err) is False

    def test_model_not_found_error(self):
        err = ModelNotFoundError("not found")
        assert is_retryable_error(err) is False

    def test_ai_validation_error(self):
        err = AIValidationError("invalid")
        assert is_retryable_error(err) is False

    def test_model_provider_500(self):
        err = ModelProviderError("server error", status_code=500)
        assert is_retryable_error(err) is True

    def test_model_provider_400(self):
        err = ModelProviderError("client error", status_code=400)
        assert is_retryable_error(err) is False

    def test_connection_error(self):
        err = ConnectionError("refused")
        assert is_retryable_error(err) is True

    def test_ai_timeout_error(self):
        err = AITimeoutError("timed out")
        assert is_retryable_error(err) is True

    def test_unknown_error(self):
        err = RuntimeError("unknown")
        assert is_retryable_error(err) is False


# ---------------------------------------------------------------------------
# get_retry_delay()
# ---------------------------------------------------------------------------


class TestGetRetryDelay:
    def test_rate_limit_with_retry_after(self):
        err = RateLimitError("rate limited", retry_after=42)
        assert get_retry_delay(err, 0) == 42.0

    def test_exponential_backoff_0(self):
        err = RuntimeError("err")
        assert get_retry_delay(err, 0) == 1  # 2^0

    def test_exponential_backoff_1(self):
        err = RuntimeError("err")
        assert get_retry_delay(err, 1) == 2  # 2^1

    def test_exponential_backoff_3(self):
        err = RuntimeError("err")
        assert get_retry_delay(err, 3) == 8  # 2^3

    def test_exponential_backoff_capped_at_60(self):
        err = RuntimeError("err")
        assert get_retry_delay(err, 10) == 60  # 2^10 = 1024, capped at 60

    def test_rate_limit_without_retry_after(self):
        err = RateLimitError("rate limited")
        delay = get_retry_delay(err, 2)
        assert delay == 4  # 2^2, falls through because retry_after is None


# ---------------------------------------------------------------------------
# categorize_error()
# ---------------------------------------------------------------------------


class TestCategorizeError:
    def test_api_key_error(self):
        assert categorize_error(APIKeyError("err")) == "authentication"

    def test_rate_limit_error(self):
        assert categorize_error(RateLimitError("err")) == "rate_limit"

    def test_model_not_found_error(self):
        assert categorize_error(ModelNotFoundError("err")) == "model_not_found"

    def test_token_limit_error(self):
        assert categorize_error(TokenLimitError("err")) == "token_limit"

    def test_ai_timeout_error(self):
        assert categorize_error(AITimeoutError("err")) == "timeout"

    def test_ai_validation_error(self):
        assert categorize_error(AIValidationError("err")) == "validation"

    def test_agent_configuration_error(self):
        assert categorize_error(AgentConfigurationError("err")) == "configuration"

    def test_model_provider_error(self):
        assert categorize_error(ModelProviderError("err")) == "provider"

    def test_analysis_error(self):
        assert categorize_error(AnalysisError("err")) == "analysis"

    def test_resource_exhausted_error(self):
        assert categorize_error(ResourceExhaustedError("err")) == "resource_exhausted"

    def test_unknown_error(self):
        assert categorize_error(RuntimeError("err")) == "unknown"


# ---------------------------------------------------------------------------
# create_error_response()
# ---------------------------------------------------------------------------


class TestCreateErrorResponse:
    def test_basic_response(self):
        err = PydanticAIException("test error", error_code="TEST")
        resp = create_error_response(err, request_id="req_123")
        assert resp["request_id"] == "req_123"
        assert resp["success"] is False
        assert "test error" in resp["error_message"]
        assert resp["retryable"] is False
        assert resp["metadata"]["error_type"] == "PydanticAIException"

    def test_pydantic_ai_exception_extras(self):
        err = PydanticAIException("err", error_code="E1", details={"foo": "bar"})
        resp = create_error_response(err, request_id="req_x")
        assert resp["error_code"] == "E1"
        assert resp["error_details"] == {"foo": "bar"}

    def test_error_category(self):
        err = RateLimitError("rate limited")
        resp = create_error_response(err, request_id="req_rl")
        assert resp["error_category"] == "rate_limit"
        assert resp["retryable"] is True

    def test_analysis_time_included(self):
        err = PydanticAIException("err")
        resp = create_error_response(err, request_id="req_t", analysis_time_ms=150.5)
        assert resp["total_analysis_time_ms"] == 150.5

    def test_non_pydantic_exception(self):
        err = RuntimeError("boom")
        resp = create_error_response(err, request_id="req_r")
        assert resp["success"] is False
        assert resp["error_category"] == "unknown"
        assert resp["retryable"] is False
        assert "error_code" not in resp

    def test_metadata_has_to_dict(self):
        err = AITimeoutError("timed out", timeout_seconds=10.0)
        resp = create_error_response(err, request_id="req_m")
        assert "type" in resp["metadata"]
        assert resp["metadata"]["type"] == "AITimeoutError"
