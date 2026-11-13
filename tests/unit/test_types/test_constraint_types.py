"""Tests for coding_client.types.constraint_types."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from coding_client.types.constraint_types import (
    SAFE_STRING_PATTERN,
    AbsolutePath,
    AnalysisID,
    CodeContent,
    Confidence,
    ContainerName,
    CPUCores,
    FutureTimestamp,
    GitHubRepoUrl,
    MemoryMB,
    Percentage,
    PortNumber,
    RelativePath,
    RequestID,
    SafeCodeString,
    SafeString,
    SafeStringLong,
    SafeStringMedium,
    SafeStringShort,
    Score,
    TimeoutSeconds,
    UserIdentifier,
    validate_absolute_path,
    validate_analysis_id,
    validate_code_content,
    validate_container_name,
    validate_future_timestamp,
    validate_github_repo_url,
    validate_relative_path,
    validate_request_id,
    validate_user_identifier,
)
from pydantic import BaseModel, ValidationError

# ---------------------------------------------------------------------------
# Standalone validator functions
# ---------------------------------------------------------------------------


class TestValidateContainerName:
    def test_valid_simple(self):
        assert validate_container_name("my-container") == "my-container"

    def test_valid_with_dot(self):
        assert validate_container_name("app.v2") == "app.v2"

    def test_valid_with_underscore(self):
        assert validate_container_name("test_1") == "test_1"

    def test_valid_numeric_start(self):
        assert validate_container_name("1abc") == "1abc"

    def test_invalid_empty(self):
        with pytest.raises(ValueError, match="Docker naming"):
            validate_container_name("")

    def test_invalid_starts_with_dash(self):
        with pytest.raises(ValueError, match="Docker naming"):
            validate_container_name("-start")

    def test_invalid_too_long(self):
        with pytest.raises(ValueError, match="too long"):
            validate_container_name("a" * 64)

    def test_invalid_special_char(self):
        with pytest.raises(ValueError, match="Docker naming"):
            validate_container_name("special@char")

    def test_valid_max_length_63(self):
        assert validate_container_name("a" * 63) == "a" * 63


class TestValidateGithubRepoUrl:
    def test_valid_url(self):
        url = "https://github.com/user/repo"
        assert validate_github_repo_url(url) == url

    def test_valid_url_with_git(self):
        url = "https://github.com/user/repo.git"
        assert validate_github_repo_url(url) == url

    def test_valid_url_trailing_slash(self):
        url = "https://github.com/user/repo/"
        assert validate_github_repo_url(url) == url

    def test_invalid_http(self):
        with pytest.raises(ValueError, match="Invalid GitHub"):
            validate_github_repo_url("http://github.com/user/repo")

    def test_invalid_gitlab(self):
        with pytest.raises(ValueError, match="Invalid GitHub"):
            validate_github_repo_url("https://gitlab.com/user/repo")

    def test_invalid_no_repo(self):
        with pytest.raises(ValueError, match="Invalid GitHub"):
            validate_github_repo_url("https://github.com/user")


class TestValidateCodeContent:
    def test_valid_code(self):
        code = "print('hello')"
        assert validate_code_content(code) == code

    def test_too_large(self):
        big = "x" * (1024 * 1024 + 1)
        with pytest.raises(ValueError, match="too large"):
            validate_code_content(big)

    def test_exactly_1mb(self):
        content = "x" * (1024 * 1024)
        assert validate_code_content(content) == content

    def test_empty_string(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_code_content("")

    def test_whitespace_only(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_code_content("   \n\t  ")


class TestValidateAbsolutePath:
    def test_valid_unix(self):
        assert validate_absolute_path("/home/user") == "/home/user"

    def test_valid_windows(self):
        assert validate_absolute_path("C:\\Users\\test") == "C:\\Users\\test"

    def test_invalid_relative(self):
        with pytest.raises(ValueError, match="must be absolute"):
            validate_absolute_path("relative/path")


class TestValidateRelativePath:
    def test_valid(self):
        assert validate_relative_path("src/main.py") == "src/main.py"

    def test_invalid_absolute(self):
        with pytest.raises(ValueError, match="must be relative"):
            validate_relative_path("/absolute")

    def test_invalid_dotdot(self):
        with pytest.raises(ValueError, match="cannot contain"):
            validate_relative_path("path/../escape")

    def test_valid_single_file(self):
        assert validate_relative_path("file.txt") == "file.txt"


class TestValidateUserIdentifier:
    def test_valid(self):
        assert validate_user_identifier("user-123") == "user-123"

    def test_too_short(self):
        with pytest.raises(ValueError, match="between 3 and 50"):
            validate_user_identifier("ab")

    def test_too_long(self):
        with pytest.raises(ValueError, match="between 3 and 50"):
            validate_user_identifier("a" * 51)

    def test_invalid_chars(self):
        with pytest.raises(ValueError, match="alphanumeric"):
            validate_user_identifier("user@name")

    def test_valid_exactly_3(self):
        assert validate_user_identifier("abc") == "abc"

    def test_valid_exactly_50(self):
        uid = "a" * 50
        assert validate_user_identifier(uid) == uid


class TestValidateRequestId:
    def test_valid(self):
        assert validate_request_id("req_abc123") == "req_abc123"

    def test_invalid_no_prefix(self):
        with pytest.raises(ValueError, match="must start with"):
            validate_request_id("abc123")

    def test_invalid_too_long(self):
        with pytest.raises(ValueError, match="too long"):
            validate_request_id("req_" + "a" * 100)

    def test_valid_minimal(self):
        assert validate_request_id("req_x") == "req_x"


class TestValidateAnalysisId:
    def test_valid(self):
        assert validate_analysis_id("anal_abc123") == "anal_abc123"

    def test_invalid_no_prefix(self):
        with pytest.raises(ValueError, match="must start with"):
            validate_analysis_id("abc123")

    def test_invalid_too_long(self):
        with pytest.raises(ValueError, match="too long"):
            validate_analysis_id("anal_" + "a" * 100)


class TestValidateFutureTimestamp:
    def test_valid_future(self):
        ts = datetime.now(UTC) + timedelta(hours=1)
        assert validate_future_timestamp(ts) == ts

    def test_invalid_past(self):
        ts = datetime.now(UTC) - timedelta(hours=1)
        with pytest.raises(ValueError, match="must be in the future"):
            validate_future_timestamp(ts)


# ---------------------------------------------------------------------------
# Annotated types in Pydantic models
# ---------------------------------------------------------------------------


class ContainerModel(BaseModel):
    name: ContainerName


class GitHubModel(BaseModel):
    url: GitHubRepoUrl


class CodeModel(BaseModel):
    code: CodeContent


class AbsolutePathModel(BaseModel):
    path: AbsolutePath


class RelativePathModel(BaseModel):
    path: RelativePath


class UserModel(BaseModel):
    user_id: UserIdentifier


class RequestModel(BaseModel):
    req_id: RequestID


class AnalysisModel(BaseModel):
    analysis_id: AnalysisID


class FutureTimestampModel(BaseModel):
    ts: FutureTimestamp


class TestAnnotatedContainerName:
    def test_valid(self):
        m = ContainerModel(name="my-app")
        assert m.name == "my-app"

    def test_invalid_empty(self):
        with pytest.raises(ValidationError):
            ContainerModel(name="")

    def test_invalid_special(self):
        with pytest.raises(ValidationError):
            ContainerModel(name="@bad")


class TestAnnotatedGitHubRepoUrl:
    def test_valid(self):
        m = GitHubModel(url="https://github.com/user/repo")
        assert m.url == "https://github.com/user/repo"

    def test_invalid(self):
        with pytest.raises(ValidationError):
            GitHubModel(url="https://gitlab.com/user/repo")


class TestAnnotatedCodeContent:
    def test_valid(self):
        m = CodeModel(code="x = 1")
        assert m.code == "x = 1"

    def test_invalid_empty(self):
        with pytest.raises(ValidationError):
            CodeModel(code="")


class TestAnnotatedAbsolutePath:
    def test_valid(self):
        m = AbsolutePathModel(path="/usr/bin")
        assert m.path == "/usr/bin"

    def test_invalid(self):
        with pytest.raises(ValidationError):
            AbsolutePathModel(path="relative")


class TestAnnotatedRelativePath:
    def test_valid(self):
        m = RelativePathModel(path="src/main.py")
        assert m.path == "src/main.py"

    def test_invalid_absolute(self):
        with pytest.raises(ValidationError):
            RelativePathModel(path="/absolute")


class TestAnnotatedUserIdentifier:
    def test_valid(self):
        m = UserModel(user_id="user-123")
        assert m.user_id == "user-123"

    def test_invalid_too_short(self):
        with pytest.raises(ValidationError):
            UserModel(user_id="ab")


class TestAnnotatedRequestID:
    def test_valid(self):
        m = RequestModel(req_id="req_abc123")
        assert m.req_id == "req_abc123"

    def test_invalid_no_prefix(self):
        with pytest.raises(ValidationError):
            RequestModel(req_id="abc123")


class TestAnnotatedAnalysisID:
    def test_valid(self):
        m = AnalysisModel(analysis_id="anal_abc123")
        assert m.analysis_id == "anal_abc123"

    def test_invalid(self):
        with pytest.raises(ValidationError):
            AnalysisModel(analysis_id="abc123")


# ---------------------------------------------------------------------------
# SafeString types
# ---------------------------------------------------------------------------


class SafeModel(BaseModel):
    text: SafeString


class SafeShortModel(BaseModel):
    text: SafeStringShort


class SafeMediumModel(BaseModel):
    text: SafeStringMedium


class SafeLongModel(BaseModel):
    text: SafeStringLong


class SafeCodeModel(BaseModel):
    text: SafeCodeString


class TestSafeString:
    def test_accepts_normal_text(self):
        m = SafeModel(text="hello world")
        assert m.text == "hello world"

    def test_accepts_empty(self):
        m = SafeModel(text="")
        assert m.text == ""

    def test_accepts_tab_newline(self):
        m = SafeModel(text="line1\nline2\ttab")
        assert "line1" in m.text

    def test_rejects_null_byte(self):
        with pytest.raises(ValidationError):
            SafeModel(text="bad\x00text")

    def test_rejects_control_0x01(self):
        with pytest.raises(ValidationError):
            SafeModel(text="bad\x01text")

    def test_rejects_del_0x7f(self):
        with pytest.raises(ValidationError):
            SafeModel(text="bad\x7ftext")

    def test_accepts_unicode(self):
        m = SafeModel(text="hello from germany")
        assert m.text == "hello from germany"


class TestSafeStringShort:
    def test_accepts_within_limit(self):
        m = SafeShortModel(text="short text")
        assert m.text == "short text"

    def test_max_256(self):
        m = SafeShortModel(text="x" * 256)
        assert len(m.text) == 256

    def test_rejects_over_256(self):
        with pytest.raises(ValidationError):
            SafeShortModel(text="x" * 257)

    def test_rejects_empty(self):
        with pytest.raises(ValidationError):
            SafeShortModel(text="")


class TestSafeStringMedium:
    def test_accepts_within_limit(self):
        m = SafeMediumModel(text="medium text")
        assert m.text == "medium text"

    def test_max_1000(self):
        m = SafeMediumModel(text="x" * 1000)
        assert len(m.text) == 1000

    def test_rejects_over_1000(self):
        with pytest.raises(ValidationError):
            SafeMediumModel(text="x" * 1001)


class TestSafeStringLong:
    def test_accepts_within_limit(self):
        m = SafeLongModel(text="long text")
        assert m.text == "long text"

    def test_max_10000(self):
        m = SafeLongModel(text="x" * 10000)
        assert len(m.text) == 10000

    def test_rejects_over_10000(self):
        with pytest.raises(ValidationError):
            SafeLongModel(text="x" * 10001)


class TestSafeCodeString:
    def test_accepts_within_limit(self):
        m = SafeCodeModel(text="print('hello')")
        assert m.text == "print('hello')"

    def test_max_50000(self):
        m = SafeCodeModel(text="x" * 50000)
        assert len(m.text) == 50000

    def test_rejects_over_50000(self):
        with pytest.raises(ValidationError):
            SafeCodeModel(text="x" * 50001)

    def test_accepts_empty(self):
        m = SafeCodeModel(text="")
        assert m.text == ""

    def test_rejects_null_byte(self):
        with pytest.raises(ValidationError):
            SafeCodeModel(text="code\x00bad")


# ---------------------------------------------------------------------------
# Numeric constraint types in models
# ---------------------------------------------------------------------------


class MemoryModel(BaseModel):
    mem: MemoryMB


class CPUModel(BaseModel):
    cpu: CPUCores


class TimeoutModel(BaseModel):
    timeout: TimeoutSeconds


class PortModel(BaseModel):
    port: PortNumber


class PercentModel(BaseModel):
    pct: Percentage


class ScoreModel(BaseModel):
    score: Score


class ConfidenceModel(BaseModel):
    conf: Confidence


class TestNumericConstraints:
    def test_memory_valid(self):
        m = MemoryModel(mem=512)
        assert m.mem == 512

    def test_memory_too_low(self):
        with pytest.raises(ValidationError):
            MemoryModel(mem=32)

    def test_cpu_valid(self):
        m = CPUModel(cpu=2.0)
        assert m.cpu == 2.0

    def test_cpu_too_low(self):
        with pytest.raises(ValidationError):
            CPUModel(cpu=0.05)

    def test_timeout_valid(self):
        m = TimeoutModel(timeout=30)
        assert m.timeout == 30

    def test_timeout_too_high(self):
        with pytest.raises(ValidationError):
            TimeoutModel(timeout=3601)

    def test_port_valid(self):
        m = PortModel(port=8080)
        assert m.port == 8080

    def test_port_zero(self):
        with pytest.raises(ValidationError):
            PortModel(port=0)

    def test_percentage_valid(self):
        m = PercentModel(pct=50.0)
        assert m.pct == 50.0

    def test_score_valid(self):
        m = ScoreModel(score=7.5)
        assert m.score == 7.5

    def test_confidence_valid(self):
        m = ConfidenceModel(conf=0.95)
        assert m.conf == 0.95

    def test_confidence_over_1(self):
        with pytest.raises(ValidationError):
            ConfidenceModel(conf=1.1)


class TestSafeStringPattern:
    def test_pattern_constant_exists(self):
        assert isinstance(SAFE_STRING_PATTERN, str)
        assert "\\x00" in SAFE_STRING_PATTERN
