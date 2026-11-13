"""Tests for coding_client.types.core_types."""

from __future__ import annotations

from coding_client.types.core_types import (
    AnalysisState,
    AnalysisType,
    CacheOperationType,
    ContainerState,
    DatabaseState,
    ErrorCategory,
    ExecutionMode,
    ExitCode,
    FileOperationType,
    GitHubEventType,
    GitHubEventTypeEnum,
    HealthState,
    NetworkOperationType,
    PRState,
    QualityLevel,
    ResponseState,
    SecurityLevel,
    SupportedLanguage,
    TestState,
    TestType,
    TransactionState,
    ValidationResult,
)


class TestLiteralTypeImports:
    """Verify all Literal type aliases can be imported and used in annotations."""

    def test_supported_language(self):
        lang: SupportedLanguage = "python"
        assert lang == "python"

    def test_execution_mode(self):
        mode: ExecutionMode = "validate"
        assert mode == "validate"

    def test_container_state(self):
        state: ContainerState = "running"
        assert state == "running"

    def test_analysis_state(self):
        state: AnalysisState = "queued"
        assert state == "queued"

    def test_response_state(self):
        state: ResponseState = "success"
        assert state == "success"

    def test_validation_result(self):
        result: ValidationResult = "valid"
        assert result == "valid"

    def test_quality_level(self):
        level: QualityLevel = "high"
        assert level == "high"

    def test_health_state(self):
        state: HealthState = "healthy"
        assert state == "healthy"

    def test_security_level(self):
        level: SecurityLevel = "critical"
        assert level == "critical"

    def test_test_type(self):
        tt: TestType = "unit"
        assert tt == "unit"

    def test_test_state(self):
        state: TestState = "passed"
        assert state == "passed"

    def test_error_category(self):
        cat: ErrorCategory = "timeout"
        assert cat == "timeout"

    def test_exit_code(self):
        code: ExitCode = 0
        assert code == 0

    def test_database_state(self):
        state: DatabaseState = "connected"
        assert state == "connected"

    def test_transaction_state(self):
        state: TransactionState = "active"
        assert state == "active"

    def test_github_event_type(self):
        event: GitHubEventType = "push"
        assert event == "push"

    def test_pr_state(self):
        state: PRState = "open"
        assert state == "open"

    def test_analysis_type(self):
        at: AnalysisType = "security"
        assert at == "security"

    def test_file_operation_type(self):
        op: FileOperationType = "read"
        assert op == "read"

    def test_network_operation_type(self):
        op: NetworkOperationType = "get"
        assert op == "get"

    def test_cache_operation_type(self):
        op: CacheOperationType = "set"
        assert op == "set"


class TestGitHubEventTypeEnum:
    def test_push_value(self):
        assert GitHubEventTypeEnum.PUSH == "push"
        assert GitHubEventTypeEnum.PUSH.value == "push"

    def test_pull_request_value(self):
        assert GitHubEventTypeEnum.PULL_REQUEST == "pull_request"

    def test_all_members(self):
        expected = {
            "PUSH",
            "PULL_REQUEST",
            "ISSUES",
            "ISSUE_COMMENT",
            "PULL_REQUEST_REVIEW",
            "PULL_REQUEST_REVIEW_COMMENT",
            "CREATE",
            "DELETE",
            "RELEASE",
        }
        assert {m.name for m in GitHubEventTypeEnum} == expected

    def test_is_str_enum(self):
        assert isinstance(GitHubEventTypeEnum.PUSH, str)

    def test_string_comparison(self):
        assert GitHubEventTypeEnum.ISSUES == "issues"
        assert str(GitHubEventTypeEnum.RELEASE) == "release"
