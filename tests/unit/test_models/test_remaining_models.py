"""Smoke tests for all remaining model files in coding_client.models.

Each section imports the main classes from a model file, creates instances
with minimal valid data, and verifies key fields and serialization.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

# ===========================================================================
# agent.py
# ===========================================================================


class TestAgentModels:
    """Tests for coding_client.models.agent."""

    def test_agent_execution_request(self):
        from coding_client.models.agent import AgentExecutionRequest

        req = AgentExecutionRequest(cli="claude", prompt="Fix the bug")
        assert req.cli == "claude"
        assert req.prompt == "Fix the bug"
        assert req.workspace == "/workspace"
        assert req.timeout == 300
        assert req.model is None
        assert req.system_prompt is None

    def test_agent_execution_response(self):
        from coding_client.models.agent import AgentExecutionResponse

        resp = AgentExecutionResponse(
            success=True,
            output="Done",
            exit_code=0,
            execution_time=2.5,
            container_name="test-container",
        )
        assert resp.success is True
        assert resp.exit_code == 0
        assert resp.session_id is None
        assert resp.cost_usd is None

    def test_agent_execution_response_with_json_fields(self):
        from coding_client.models.agent import AgentExecutionResponse

        resp = AgentExecutionResponse(
            success=True,
            output="Result",
            exit_code=0,
            execution_time=1.0,
            container_name="c1",
            session_id="sess-123",
            cost_usd=0.05,
            duration_ms=1000,
            usage={"input_tokens": 100, "output_tokens": 50},
        )
        assert resp.session_id == "sess-123"
        assert resp.cost_usd == 0.05
        data = resp.model_dump()
        assert "usage" in data


# ===========================================================================
# ai_test_failure.py
# ===========================================================================


class TestAITestFailureModels:
    """Tests for coding_client.models.ai_test_failure."""

    def test_test_framework_enum(self):
        from coding_client.models.ai_test_failure import TestFramework

        assert TestFramework.PYTEST == "pytest"
        assert TestFramework.UNKNOWN == "unknown"

    def test_failure_type_enum(self):
        from coding_client.models.ai_test_failure import FailureType

        assert FailureType.ASSERTION_ERROR == "assertion_error"

    def test_severity_level_enum(self):
        from coding_client.models.ai_test_failure import SeverityLevel

        assert SeverityLevel.CRITICAL == "critical"

    def test_test_failure_context(self):
        from coding_client.models.ai_test_failure import TestFailureContext

        ctx = TestFailureContext(test_name="test_add")
        assert ctx.test_name == "test_add"
        assert ctx.test_class is None

    def test_test_failure_data(self):
        from coding_client.models.ai_test_failure import TestFailureContext, TestFailureData

        ctx = TestFailureContext(test_name="test_add")
        data = TestFailureData(
            failure_id="fail-001",
            raw_output="AssertionError: 1 != 2",
            context=ctx,
        )
        assert data.failure_id == "fail-001"

    def test_test_failure_data_invalid_id(self):
        from coding_client.models.ai_test_failure import TestFailureContext, TestFailureData

        ctx = TestFailureContext(test_name="test_add")
        with pytest.raises(ValidationError, match="alphanumeric"):
            TestFailureData(
                failure_id="bad id!",
                raw_output="error",
                context=ctx,
            )

    def test_root_cause(self):
        from coding_client.models.ai_test_failure import RootCause

        rc = RootCause(
            cause_id="rc-001",
            category="logic_error",
            description="Off-by-one error in loop iteration logic",
            severity="high",
            confidence="high",
            confidence_score=0.85,
        )
        assert rc.cause_id == "rc-001"
        assert rc.category == "logic_error"

    def test_root_cause_confidence_mismatch(self):
        from coding_client.models.ai_test_failure import RootCause

        with pytest.raises(ValidationError, match="VERY_HIGH confidence must have score"):
            RootCause(
                cause_id="rc-002",
                category="logic_error",
                description="Off-by-one error in loop iteration logic",
                severity="high",
                confidence="very_high",
                confidence_score=0.5,
            )

    def test_fix_suggestion(self):
        from coding_client.models.ai_test_failure import FixSuggestion

        fs = FixSuggestion(
            suggestion_id="fix-001",
            title="Fix loop boundary condition",
            description="Change the loop to use '<=' instead of '<' to include the last element",
            fix_type="code_change",
            priority="high",
            confidence="high",
            confidence_score=0.8,
            estimated_effort="low",
        )
        assert fs.fix_type == "code_change"

    def test_failure_analysis_request(self):
        from coding_client.models.ai_test_failure import (
            FailureAnalysisRequest,
            TestFailureContext,
            TestFailureData,
        )

        ctx = TestFailureContext(test_name="test_x")
        fd = TestFailureData(failure_id="f1", raw_output="error", context=ctx)
        req = FailureAnalysisRequest(request_id="req-001", failure_data=fd)
        assert req.max_root_causes == 5
        assert req.include_patterns is True


# ===========================================================================
# analysis.py
# ===========================================================================


class TestAnalysisModels:
    """Tests for coding_client.models.analysis."""

    def test_deep_analysis_request(self):
        from coding_client.models.analysis import DeepAnalysisRequest

        req = DeepAnalysisRequest()
        assert req.include_security is True
        assert req.include_performance is True

    def test_bug_hunting_request(self):
        from coding_client.models.analysis import BugHuntingRequest

        req = BugHuntingRequest(error_logs="traceback line 1")
        assert req.error_logs == "traceback line 1"
        assert req.create_pr is False

    def test_improvement_item_requires_code(self):
        from coding_client.models.analysis import ImprovementItem

        with pytest.raises(ValidationError, match="fixed_code or code"):
            ImprovementItem(file_path="a.py")

    def test_improvement_item_with_fixed_code(self):
        from coding_client.models.analysis import ImprovementItem

        item = ImprovementItem(file_path="a.py", fixed_code="print('hello')")
        assert item.file_path == "a.py"

    def test_improvement_request(self):
        from coding_client.models.analysis import ImprovementItem, ImprovementRequest

        item = ImprovementItem(file_path="a.py", code="x = 1")
        req = ImprovementRequest(
            github_repo="owner/repo",
            GITHUB_ACCESS_TOKEN="ghp_token123",
            updates=[item],
        )
        assert req.github_repo == "owner/repo"

    def test_code_validation_request(self):
        from coding_client.models.analysis import CodeValidationRequest

        req = CodeValidationRequest(
            code="def foo(): pass",
            filename="foo.py",
            language="python",
            author="dev",
            description="Add foo",
        )
        assert req.language == "python"


# ===========================================================================
# bug.py
# ===========================================================================


class TestBugModels:
    """Tests for coding_client.models.bug."""

    def test_error_type_enum(self):
        from coding_client.models.bug import ErrorType

        assert ErrorType.SYNTAX_ERROR.value == "syntax_error"
        assert ErrorType.IMPORT_ERROR.value == "import_error"

    def test_parsed_error(self):
        from coding_client.models.bug import ErrorType, ParsedError

        err = ParsedError(
            error_type=ErrorType.IMPORT_ERROR,
            message="No module named 'foo'",
            file_path="main.py",
            line_number=1,
            function_name=None,
            stack_trace=[],
            confidence=0.9,
        )
        assert err.error_type == ErrorType.IMPORT_ERROR
        assert err.confidence == 0.9

    def test_code_fix(self):
        from coding_client.models.bug import CodeFix

        fix = CodeFix(
            file_path="req.txt",
            line_number=None,
            original_code="",
            fixed_code="requests>=2.0",
            explanation="Add missing dependency",
            confidence=0.95,
        )
        assert fix.confidence == 0.95

    def test_bug_analysis_result(self):
        from coding_client.models.bug import BugAnalysisResult

        result = BugAnalysisResult(
            errors=[],
            resolves=[],
            root_cause_analysis="Missing dep",
            fix_summary="Add to requirements",
            estimated_effort="Low",
            risk_assessment="Minimal",
        )
        assert result.estimated_effort == "Low"

    def test_bug_fix_validation_result(self):
        from coding_client.models.bug import BugFixValidationResult

        r = BugFixValidationResult(
            is_safe=True,
            confidence=0.9,
            warnings=[],
            suggestions=["Run tests"],
            risk_level="low",
        )
        assert r.is_safe is True


# ===========================================================================
# code_graph.py
# ===========================================================================


class TestCodeGraphModels:
    """Tests for coding_client.models.code_graph."""

    def test_codebase_init_request(self):
        from coding_client.models.code_graph import CodebaseInitRequest

        req = CodebaseInitRequest(container_name="codegraph-proj")
        assert req.container_name == "codegraph-proj"
        assert req.codebase_path is None

    def test_codebase_init_request_dangerous_path_rejected(self):
        from coding_client.models.code_graph import CodebaseInitRequest

        with pytest.raises(ValidationError, match="system directories"):
            CodebaseInitRequest(container_name="test-proj", codebase_path="/etc")

    def test_code_graph_analysis_request(self):
        from coding_client.models.code_graph import CodeGraphAnalysisRequest

        req = CodeGraphAnalysisRequest()
        assert req.analysis_depth == "full"

    def test_node_query(self):
        from coding_client.models.code_graph import NodeQuery

        q = NodeQuery(type="function", limit=50)
        assert q.limit == 50

    def test_node_response(self):
        from coding_client.models.code_graph import NodeResponse

        r = NodeResponse(id="n1", type="function", properties={"name": "main"})
        assert r.id == "n1"

    def test_init_response(self):
        from coding_client.models.code_graph import InitResponse

        r = InitResponse(
            message="done",
            container_name="c1",
            graph_db_path="/db",
            nodes_created=100,
            edges_created=50,
            status="ready",
        )
        assert r.nodes_created == 100

    def test_pattern_search_request(self):
        from coding_client.models.code_graph import PatternSearchRequest

        req = PatternSearchRequest(pattern="def.*async")
        assert req.pattern == "def.*async"


# ===========================================================================
# container.py
# ===========================================================================


class TestContainerModels:
    """Tests for coding_client.models.container."""

    def test_container_status_enum(self):
        from coding_client.models.container import ContainerStatus

        assert ContainerStatus.RUNNING == "running"
        assert ContainerStatus.STOPPED == "stopped"

    def test_container_info(self):
        from coding_client.models.container import ContainerInfo, ContainerStatus

        info = ContainerInfo(
            container_name="test-c",
            api_endpoint="http://localhost:8700",
            codebase_path="/app/repo",
            repo_url="https://github.com/o/r",
            branch="main",
            status=ContainerStatus.RUNNING,
        )
        assert info.container_name == "test-c"
        assert info.graph_initialized is False

    def test_github_repo_request(self):
        from coding_client.models.container import GitHubRepoRequest

        req = GitHubRepoRequest(repo_url="https://github.com/owner/repo")
        assert req.branch == "main"

    def test_github_repo_request_invalid_url(self):
        from coding_client.models.container import GitHubRepoRequest

        with pytest.raises(ValidationError):
            GitHubRepoRequest(repo_url="not-a-url")

    def test_container_spec(self):
        from coding_client.models.container import ContainerSpec

        spec = ContainerSpec(name="web", image="node:18", port=3000)
        assert spec.port == 3000

    def test_analysis_config(self):
        from coding_client.models.container import AnalysisConfig

        ac = AnalysisConfig(include_tests=True, language_hint="python")
        assert ac.include_tests is True


# ===========================================================================
# docker_container.py
# ===========================================================================


class TestDockerContainerModels:
    """Tests for coding_client.models.docker_container."""

    def test_docker_container_details(self):
        from coding_client.models.container import ContainerStatus
        from coding_client.models.docker_container import DockerContainerDetails

        d = DockerContainerDetails(
            docker_id="abc123",
            container_name="test-c",
            image="python:3.11",
            ports={"8700/tcp": 8700},
            workspace_path="/workspace",
            status=ContainerStatus.RUNNING,
        )
        assert d.docker_id == "abc123"
        assert d.status == ContainerStatus.RUNNING

    def test_to_container_info(self):
        from coding_client.models.container import ContainerStatus
        from coding_client.models.docker_container import DockerContainerDetails

        d = DockerContainerDetails(
            docker_id="abc",
            container_name="c1",
            image="img",
            ports={"8700/tcp": 8700},
            workspace_path="/ws",
            status=ContainerStatus.RUNNING,
        )
        info = d.to_container_info(repo_url="https://github.com/o/r")
        assert info.container_name == "c1"
        assert "8700" in info.api_endpoint


# ===========================================================================
# github.py
# ===========================================================================


class TestGitHubModels:
    """Tests for coding_client.models.github."""

    def _make_user(self):
        from coding_client.models.github import GitHubUser

        return GitHubUser(
            login="dev",
            id=1,
            avatar_url="https://avatar.url",
            url="https://api.github.com/users/dev",
            type="User",
        )

    def test_github_user(self):
        u = self._make_user()
        assert u.login == "dev"

    def test_github_repository(self):
        from coding_client.models.github import GitHubRepository

        r = GitHubRepository(
            id=1,
            name="repo",
            full_name="owner/repo",
            url="https://github.com/owner/repo",
            clone_url="https://github.com/owner/repo.git",
            ssh_url="git@github.com:owner/repo.git",
            default_branch="main",
            size=1024,
            stargazers_count=10,
            forks_count=2,
            open_issues_count=5,
            private=False,
            owner=self._make_user(),
        )
        assert r.full_name == "owner/repo"

    def test_pull_request_data(self):
        from coding_client.models.github import PullRequestData

        now = datetime.now(UTC)
        pr = PullRequestData(
            number=42,
            title="Add feature",
            state="open",
            author="dev",
            created_at=now,
            updated_at=now,
            base_branch="main",
            head_branch="feature",
            url="https://github.com/o/r/pull/42",
            diff_url="https://github.com/o/r/pull/42.diff",
            patch_url="https://github.com/o/r/pull/42.patch",
        )
        assert pr.number == 42

    def test_clone_result(self):
        from coding_client.models.github import CloneResult

        r = CloneResult(success=True, repo_id="r1", local_path="/tmp/repo")
        assert r.success is True

    def test_code_snippet(self):
        from coding_client.models.github import CodeSnippet

        s = CodeSnippet(code="x = 1", language="python")
        assert s.language == "python"

    def test_pr_file_change(self):
        from coding_client.models.github import PRFileChange

        c = PRFileChange(file_path="a.py", change_type="modified")
        assert c.additions == 0

    def test_github_repo_info(self):
        from coding_client.models.github import GitHubRepoInfo

        info = GitHubRepoInfo(owner="me", name="proj", url="https://github.com/me/proj")
        assert info.default_branch == "main"


# ===========================================================================
# logging.py
# ===========================================================================


class TestLoggingModels:
    """Tests for coding_client.models.logging."""

    def test_log_level_values(self):
        from coding_client.models.logging import LogLevel

        assert LogLevel.DEBUG == "DEBUG"
        assert LogLevel.INFO == "INFO"
        assert LogLevel.WARNING == "WARNING"
        assert LogLevel.ERROR == "ERROR"
        assert LogLevel.CRITICAL == "CRITICAL"

    def test_from_lowercase(self):
        from coding_client.models.logging import LogLevel

        assert LogLevel.from_lowercase("info") == LogLevel.INFO

    def test_to_lowercase(self):
        from coding_client.models.logging import LogLevel

        assert LogLevel.ERROR.to_lowercase() == "error"


# ===========================================================================
# package_manager.py
# ===========================================================================


class TestPackageManagerModels:
    """Tests for coding_client.models.package_manager."""

    def test_system_package_manager_enum(self):
        from coding_client.models.package_manager import SystemPackageManager

        assert SystemPackageManager.APT.value == "apt-get"
        assert SystemPackageManager.BREW.value == "brew"

    def test_system_package_manager_install_command(self):
        from coding_client.models.package_manager import SystemPackageManager

        cmd = SystemPackageManager.APT.install_command
        assert "apt-get" in cmd

    def test_language_package_manager_enum(self):
        from coding_client.models.package_manager import LanguagePackageManager

        assert LanguagePackageManager.PIP.value == "pip"
        assert LanguagePackageManager.NPM.value == "npm"
        assert LanguagePackageManager.CARGO.value == "cargo"

    def test_language_package_manager_manifest_files(self):
        from coding_client.models.package_manager import LanguagePackageManager

        files = LanguagePackageManager.NPM.manifest_files
        assert "package.json" in files

    def test_external_package(self):
        from coding_client.models.package_manager import ExternalPackage

        pkg = ExternalPackage(name="requests", version=">=2.28.0")
        assert pkg.name == "requests"
        assert pkg.is_dev is False
        assert pkg.full_spec == "requests>=2.28.0"

    def test_external_package_with_extras(self):
        from coding_client.models.package_manager import ExternalPackage

        pkg = ExternalPackage(name="pydantic", version=">=2.0", extras=["email", "dotenv"])
        assert pkg.full_spec == "pydantic[email,dotenv]>=2.0"

    def test_system_dependency(self):
        from coding_client.models.package_manager import (
            SystemDependency,
            SystemPackageManager,
        )

        dep = SystemDependency(
            name="libssl",
            packages={SystemPackageManager.APT: ["libssl-dev"]},
            description="OpenSSL development libraries",
        )
        assert dep.name == "libssl"

    def test_package_manager_capability(self):
        from coding_client.models.package_manager import (
            LanguagePackageManager,
            PackageManagerCapability,
        )

        cap = PackageManagerCapability(
            manager=LanguagePackageManager.POETRY,
            supports_lockfile=True,
            supports_virtual_env=True,
            supports_dev_dependencies=True,
        )
        assert cap.supports_lockfile is True


# ===========================================================================
# pr_validation.py
# ===========================================================================


class TestPRValidationModels:
    """Tests for coding_client.models.pr_validation."""

    def test_file_type_enum(self):
        from coding_client.models.pr_validation import FileType

        assert FileType.PYTHON.value == "python"

    def test_risk_level_enum(self):
        from coding_client.models.pr_validation import RiskLevel

        assert RiskLevel.CRITICAL.value == "CRITICAL"

    def test_diff_stats(self):
        from coding_client.models.pr_validation import DiffStats

        ds = DiffStats(
            total_files=5,
            total_additions=100,
            total_deletions=20,
            files_added=2,
            files_deleted=1,
            files_modified=2,
            files_renamed=0,
        )
        assert ds.total_files == 5

    def test_validation_file_change(self):
        from coding_client.models.pr_validation import (
            FileType,
            ValidationFileChange,
        )
        from coding_client.models.static_analysis import StaticAnalysisChangeType

        fc = ValidationFileChange(
            filename="a.py",
            file_type=FileType.PYTHON,
            change_type=StaticAnalysisChangeType.MODIFIED,
            additions=10,
            deletions=5,
            patch="@@ -1,5 +1,10 @@",
        )
        assert fc.total_changes == 15

    def test_pr_diff_change_complexity(self):
        from coding_client.models.pr_validation import (
            DiffStats,
            FileType,
            PRDiff,
            ValidationFileChange,
        )
        from coding_client.models.static_analysis import StaticAnalysisChangeType

        fc = ValidationFileChange(
            filename="a.py",
            file_type=FileType.PYTHON,
            change_type=StaticAnalysisChangeType.MODIFIED,
            additions=50,
            deletions=50,
            patch="@@ @@",
        )
        diff = PRDiff(
            base_sha="abc",
            head_sha="def",
            files_changed=[fc],
            stats=DiffStats.from_files([fc]),
            metadata={},
        )
        assert diff.change_complexity == 1.0

    def test_validation_issue(self):
        from coding_client.models.pr_validation import ValidationIssue

        vi = ValidationIssue(type="error", severity="HIGH", message="Problem", file="a.py")
        assert vi.file == "a.py"

    def test_validation_result(self):
        from coding_client.models.pr_validation import RiskLevel, ValidationResult

        vr = ValidationResult(
            validation_type="type_check",
            passed=True,
            score=0.95,
            risk_level=RiskLevel.LOW,
            issues=[],
            recommendations=[],
        )
        assert vr.critical_issues == []


# ===========================================================================
# pydantic_ai.py
# ===========================================================================


class TestPydanticAIModels:
    """Tests for coding_client.models.pydantic_ai."""

    def test_analysis_type_enum(self):
        from coding_client.models.pydantic_ai import PydanticAIAnalysisType

        assert PydanticAIAnalysisType.FAILURE_ANALYSIS == "failure_analysis"

    def test_failure_severity_enum(self):
        from coding_client.models.pydantic_ai import FailureSeverity

        assert FailureSeverity.CRITICAL == "critical"

    def test_test_failure_context(self):
        from coding_client.models.pydantic_ai import PydanticAITestFailureContext

        ctx = PydanticAITestFailureContext(
            test_id="t1",
            language="python",
            test_type="unit",
            exit_code=1,
            execution_time_ms=500.0,
        )
        assert ctx.test_id == "t1"
        assert ctx.stdout == ""

    def test_negative_execution_time_rejected(self):
        from coding_client.models.pydantic_ai import PydanticAITestFailureContext

        with pytest.raises(ValidationError, match="negative"):
            PydanticAITestFailureContext(
                test_id="t1",
                language="python",
                test_type="unit",
                exit_code=1,
                execution_time_ms=-1.0,
            )

    def test_failure_analysis_result(self):
        from coding_client.models.pydantic_ai import (
            FailureAnalysisResult,
            FailureCategory,
            FailureSeverity,
            PydanticAIAnalysisType,
        )

        r = FailureAnalysisResult(
            analysis_id="a1",
            test_id="t1",
            analysis_type=PydanticAIAnalysisType.FAILURE_ANALYSIS,
            category=FailureCategory.ASSERTION_ERROR,
            severity=FailureSeverity.HIGH,
            confidence=0.8,
            root_cause="Assertion failed",
            analysis_duration_ms=100.0,
            ai_model_provider="openai",
            ai_model_name="gpt-4",
        )
        assert r.confidence == 0.8

    def test_agent_configuration(self):
        from coding_client.models.pydantic_ai import AgentConfiguration

        cfg = AgentConfiguration(
            agent_id="agent-1",
            ai_model_provider="openai",
            ai_model_name="gpt-4",
        )
        assert cfg.max_retries == 3
        assert cfg.temperature == 0.1

    def test_agent_metrics(self):
        from coding_client.models.pydantic_ai import AgentMetrics

        m = AgentMetrics(agent_id="a1")
        assert m.total_requests == 0
        assert m.error_rate == 0.0


# ===========================================================================
# repo_scanner.py
# ===========================================================================


class TestRepoScannerModels:
    """Tests for coding_client.models.repo_scanner."""

    def test_repo_scan_action_enum(self):
        from coding_client.models.repo_scanner import RepoScanAction

        assert RepoScanAction.DEPENDENCIES == "dependencies"
        assert RepoScanAction.FULL_SCAN == "full_scan"

    def test_scan_request(self):
        from coding_client.models.repo_scanner import RepoScanAction, RepoScannerScanRequest

        req = RepoScannerScanRequest(container_name="c1", action=RepoScanAction.IMPORTS)
        assert req.container_name == "c1"

    def test_dependency_validation(self):
        from coding_client.models.repo_scanner import DependencyValidation

        dv = DependencyValidation(name="requests", version="2.31.0", source="pip", valid=True)
        assert dv.valid is True

    def test_scanner_validation_error(self):
        from coding_client.models.repo_scanner import ScannerValidationError

        e = ScannerValidationError(type="SyntaxError", message="invalid syntax")
        assert e.type == "SyntaxError"

    def test_base_scan_response(self):
        from coding_client.models.repo_scanner import BaseScanResponse

        r = BaseScanResponse(
            container_name="c1",
            action="dependencies",
            scan_duration=1.5,
            file_count=10,
            request_id="r1",
        )
        assert r.scan_duration == 1.5


# ===========================================================================
# security.py
# ===========================================================================


class TestSecurityModels:
    """Tests for coding_client.models.security."""

    def test_security_level_enum(self):
        from coding_client.models.security import SecurityLevel

        assert SecurityLevel.LOW == "low"
        assert SecurityLevel.CRITICAL == "critical"

    def test_security_violation(self):
        from coding_client.models.security import SecurityLevel, SecurityViolation

        v = SecurityViolation(
            type="command_injection",
            severity=SecurityLevel.HIGH,
            pattern_matched="os.system",
            description="Dangerous command execution",
        )
        assert v.type == "command_injection"

    def test_security_validation_request(self):
        from coding_client.models.security import SecurityValidationRequest

        req = SecurityValidationRequest(code="import os", language="python")
        assert req.security_level == "medium"

    def test_security_validation_result(self):
        from coding_client.models.security import SecurityValidationResult

        r = SecurityValidationResult(is_safe=True, risk_score=5.0)
        assert r.is_safe is True
        assert r.violations == []

    def test_risk_score_bounds(self):
        from coding_client.models.security import SecurityValidationResult

        with pytest.raises(ValidationError):
            SecurityValidationResult(is_safe=False, risk_score=101.0)

    def test_osv_vulnerability(self):
        from coding_client.models.security import OSVVulnerability

        v = OSVVulnerability(
            id="GHSA-1234",
            summary="XSS vulnerability",
            package_name="lodash",
            ecosystem="npm",
        )
        assert v.id == "GHSA-1234"

    def test_package_info(self):
        from coding_client.models.security import PackageInfo

        pi = PackageInfo(name="requests", version="2.31.0", ecosystem="PyPI")
        assert pi.ecosystem == "PyPI"


# ===========================================================================
# static_analysis.py
# ===========================================================================


class TestStaticAnalysisModels:
    """Tests for coding_client.models.static_analysis."""

    def test_output_format_enum(self):
        from coding_client.models.static_analysis import OutputFormat

        assert OutputFormat.JSON == "json"
        assert OutputFormat.SVG == "svg"

    def test_language_enum(self):
        from coding_client.models.static_analysis import Language

        assert Language.PYTHON == "python"

    def test_change_type_enum(self):
        from coding_client.models.static_analysis import StaticAnalysisChangeType

        assert StaticAnalysisChangeType.ADDED == "ADDED"

    def test_call_graph_request(self):
        from coding_client.models.static_analysis import CallGraphRequest

        req = CallGraphRequest(container_name="c1")
        assert req.max_depth == 10
        assert req.include_external is False

    def test_code_change(self):
        from coding_client.models.static_analysis import (
            CodeChange,
            StaticAnalysisChangeType,
        )

        cc = CodeChange(
            file_path="a.py",
            modified_code="print('hi')",
            change_type=StaticAnalysisChangeType.MODIFIED,
        )
        assert cc.file_path == "a.py"

    def test_symbolic_execution_result(self):
        from coding_client.models.static_analysis import SymbolicExecutionResult

        r = SymbolicExecutionResult(status="complete")
        assert r.edge_cases_found == []

    def test_security_issue(self):
        from coding_client.models.static_analysis import SecurityIssue

        si = SecurityIssue(
            severity="high",
            type="sql_injection",
            location="main.py:10",
            flow_path=["input", "query"],
            recommendation="Use parameterized queries",
        )
        assert si.severity == "high"

    def test_documentation_request(self):
        from coding_client.models.static_analysis import (
            DocumentationRequest,
            DocumentationType,
        )

        req = DocumentationRequest(
            container_name="c1",
            doc_types=[DocumentationType.API_REFERENCE],
        )
        assert req.include_diagrams is True

    def test_call_graph_analysis_db_model(self):
        from coding_client.models.static_analysis import CallGraphAnalysis

        cga = CallGraphAnalysis(
            id="a1",
            repository_url="https://github.com/o/r",
            analysis_config={},
            call_graph_data={},
            visual_outputs={},
            created_at="2024-01-01",
        )
        assert cga.id == "a1"


# ===========================================================================
# system.py
# ===========================================================================


class TestSystemModels:
    """Tests for coding_client.models.system."""

    def test_package_manager_enum(self):
        from coding_client.models.system import PackageManager

        assert PackageManager.APT.value == "apt"
        assert PackageManager.APT.command == "apt-get"

    def test_dependency_type_enum(self):
        from coding_client.models.system import DependencyType

        assert DependencyType.BUILD.value == "build"
        assert DependencyType.RUNTIME.value == "runtime"

    def test_system_dependency(self):
        from coding_client.models.system import DependencyType, PackageManager, SystemDependency

        dep = SystemDependency(
            name="openssl",
            packages={PackageManager.APT: ["libssl-dev"]},
            description="OpenSSL",
        )
        assert dep.name == "openssl"
        assert dep.dependency_type == DependencyType.RUNTIME


# ===========================================================================
# test_executor.py
# ===========================================================================


class TestTestExecutorModels:
    """Tests for coding_client.models.test_executor."""

    def test_code_validation_request(self):
        from coding_client.models.test_executor import CodeValidationRequest

        req = CodeValidationRequest(code="print('hello')")
        assert req.code == "print('hello')"
        assert req.filename is None
        assert req.strict_mode is False

    def test_code_validation_response(self):
        from coding_client.models.test_executor import CodeValidationResponse

        resp = CodeValidationResponse(validationId="v1", valid=True)
        assert resp.valid is True
        assert resp.errors == []

    def test_validation_error_response(self):
        from coding_client.models.test_executor import TestExecutorValidationError

        err = TestExecutorValidationError(error="Syntax error at line 5")
        assert err.error == "Syntax error at line 5"

    def test_validate_code_size(self):
        from coding_client.models.test_executor import validate_code_size

        assert validate_code_size("x = 1") is True
        assert validate_code_size("x" * 2_000_000) is False

    def test_sanitize_error_output(self):
        from coding_client.models.test_executor import sanitize_error_output

        raw = "Error in /app/test_workspace/foo.py: bad"
        clean = sanitize_error_output(raw)
        assert "/app/test_workspace/" not in clean
        assert "foo.py" in clean

    def test_sanitize_truncates(self):
        from coding_client.models.test_executor import sanitize_error_output

        result = sanitize_error_output("x" * 2000, max_length=100)
        assert len(result) == 100
        assert result.endswith("...")


# ===========================================================================
# testing_config.py
# ===========================================================================


class TestTestingConfigModels:
    """Tests for coding_client.models.testing_config."""

    def test_testing_configuration_defaults(self):
        from coding_client.models.testing_config import TestingConfiguration

        cfg = TestingConfiguration()
        assert cfg.default_timeout == 30
        assert cfg.max_memory_mb == 512
        assert cfg.network_isolation is True
        assert cfg.python_version == "3.11"
        assert cfg.enabled_python_tools == ["ruff", "ruff-format", "ty", "bandit"]

    def test_dependency_scan_config(self):
        from coding_client.models.testing_config import DependencyScanConfig

        cfg = DependencyScanConfig()
        assert cfg.enabled is True
        assert cfg.scan_dev_dependencies is False

    def test_quality_scan_config(self):
        from coding_client.models.testing_config import QualityScanConfig

        cfg = QualityScanConfig()
        assert cfg.parallel_tool_execution is True

    def test_background_task_config(self):
        from coding_client.models.testing_config import BackgroundTaskConfig

        cfg = BackgroundTaskConfig()
        assert cfg.max_concurrent_tasks == 5

    def test_task_execution_result(self):
        from coding_client.models.testing_config import TaskExecutionResult

        r = TaskExecutionResult(
            task_id="t1",
            task_type="quality_scan",
            success=True,
            start_time=datetime.now(UTC),
        )
        assert r.task_id == "t1"

    def test_task_queue_config(self):
        from coding_client.models.testing_config import TestingTaskQueueConfig

        cfg = TestingTaskQueueConfig(queue_name="test-queue")
        assert cfg.max_queue_size == 1000

    def test_factory_functions(self):
        from coding_client.models.testing_config import (
            get_default_background_task_config,
            get_default_dependency_scan_config,
            get_default_quality_scan_config,
            get_default_testing_config,
        )

        assert get_default_testing_config().default_timeout == 30
        assert get_default_dependency_scan_config().enabled is True
        assert get_default_quality_scan_config().parallel_tool_execution is True
        assert get_default_background_task_config().max_concurrent_tasks == 5


# ===========================================================================
# testing.py
# ===========================================================================


class TestTestingModels:
    """Tests for coding_client.models.testing."""

    def test_test_type_enum(self):
        from coding_client.models.testing import TestType

        assert TestType.UNIT == "unit"
        assert TestType.INTEGRATION == "integration"

    def test_resource_limits(self):
        from coding_client.models.testing import ResourceLimits

        rl = ResourceLimits(memory_mb=512, cpu_cores=2.0)
        assert rl.memory_mb == 512

    def test_test_security_level_enum(self):
        from coding_client.models.testing import TestSecurityLevel

        assert TestSecurityLevel.HIGH == "high"

    def test_test_request_with_code(self):
        from coding_client.models.testing import TestRequest

        req = TestRequest(
            code="def add(a,b): return a+b",
            test_code="assert add(1,2)==3",
            language="python",
        )
        assert req.language == "python"
        assert req.security_level == "high"

    def test_test_request_missing_code_raises(self):
        from coding_client.models.testing import TestRequest

        with pytest.raises(ValidationError, match="code"):
            TestRequest(test_code="assert True", language="python")

    def test_test_request_missing_test_raises(self):
        from coding_client.models.testing import TestRequest

        with pytest.raises(ValidationError, match="test_code"):
            TestRequest(code="x = 1", language="python")

    def test_test_result(self):
        from coding_client.models.testing import TestResult, TestSecurityLevel

        r = TestResult(
            test_id="t1",
            success=True,
            exit_code=0,
            execution_time=1.0,
            created_at=datetime.now(UTC),
            language="python",
            security_level=TestSecurityLevel.MEDIUM,
        )
        assert r.success is True
        data = r.model_dump()
        assert "test_id" in data

    def test_quality_request(self):
        from coding_client.models.testing import QualityRequest

        req = QualityRequest(container_name="c1", code="x = 1")
        assert req.container_name == "c1"

    def test_quality_result(self):
        from coding_client.models.testing import QualityResult

        r = QualityResult(
            analysis_id="a1",
            overall_score=85.0,
            total_issues=0,
            execution_time=2.0,
            created_at=datetime.now(UTC),
            language="python",
        )
        assert r.overall_score == 85.0

    def test_quality_result_create_failed(self):
        from coding_client.models.testing import QualityResult

        r = QualityResult.create_failed_result(error_message="Crash")
        assert r.success is False
        assert r.error == "Crash"
        assert r.overall_score == 0.0

    def test_command_result(self):
        from coding_client.models.testing import CommandResult

        cr = CommandResult(exit_code=0, execution_time=0.5)
        assert cr.timeout is False

    def test_test_execution_status_enum(self):
        from coding_client.models.testing import TestExecutionStatus

        assert TestExecutionStatus.PENDING == "pending"
        assert TestExecutionStatus.COMPLETED == "completed"

    def test_test_execution_info(self):
        from coding_client.models.testing import TestExecutionInfo, TestExecutionStatus

        now = datetime.now(UTC)
        info = TestExecutionInfo(
            execution_id="e1",
            status=TestExecutionStatus.RUNNING,
            started_at=now,
            updated_at=now,
        )
        assert info.status == TestExecutionStatus.RUNNING

    def test_create_test_request_factory(self):
        from coding_client.models.testing import create_test_request

        req = create_test_request(
            code="x = 1",
            language="python",
            container_name="c1",
            test_code="assert x == 1",
        )
        assert req.container_name == "c1"

    def test_create_test_result_factory(self):
        from coding_client.models.testing import create_test_result

        r = create_test_result(success=True, container_name="c1")
        assert r.success is True
        assert r.container_name == "c1"


# ===========================================================================
# validation.py
# ===========================================================================


class TestValidationModels:
    """Tests for coding_client.models.validation."""

    def test_validation_request_base(self):
        from coding_client.models.validation import ValidationRequest

        req = ValidationRequest(code="x = 1")
        assert req.code == "x = 1"

    def test_python_validation_request(self):
        from coding_client.models.validation import PythonValidationRequest

        req = PythonValidationRequest(code="print('hi')")
        assert req.filename == "test.py"

    def test_java_validation_request(self):
        from coding_client.models.validation import JavaValidationRequest

        req = JavaValidationRequest(code="class Test {}")
        assert req.className == "Test"

    def test_rust_validation_request(self):
        from coding_client.models.validation import RustValidationRequest

        req = RustValidationRequest(code="fn main() {}")
        assert req.crateType == "bin"

    def test_csharp_validation_request(self):
        from coding_client.models.validation import CSharpValidationRequest

        req = CSharpValidationRequest(code="class X {}")
        assert req.projectType == "console"
        assert req.targetFramework == "net8.0"

    def test_go_validation_request(self):
        from coding_client.models.validation import GoValidationRequest

        req = GoValidationRequest(code="package main")
        assert req.filename == "main.go"

    def test_javascript_validation_request(self):
        from coding_client.models.validation import JavaScriptValidationRequest

        req = JavaScriptValidationRequest(code="const x = 1;")
        assert req.filename == "test.js"

    def test_validation_response(self):
        from coding_client.models.validation import ValidationResponse

        resp = ValidationResponse(validationId="v1", valid=True)
        assert resp.valid is True
        assert resp.errors == []

    def test_code_validation_error_response(self):
        from coding_client.models.validation import CodeValidationErrorResponse

        resp = CodeValidationErrorResponse(error="Parse failed")
        assert resp.valid is False
        assert resp.error == "Parse failed"

    def test_extra_fields_rejected(self):
        from coding_client.models.validation import ValidationRequest

        with pytest.raises(ValidationError):
            ValidationRequest(code="x = 1", extra_field="not allowed")
