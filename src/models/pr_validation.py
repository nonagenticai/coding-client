"""Pull request validation models for comprehensive change analysis.

This module provides sophisticated data models for analyzing pull request changes,
validating their impact, and generating actionable recommendations. The models
support detailed diff analysis, semantic change detection, and risk assessment
for code modifications.

The PR validation system enables:
- Comprehensive diff analysis with file-level change tracking
- Semantic analysis of code modifications using AST comparison
- Breaking change detection across API surfaces
- Impact assessment on tests, documentation, and dependencies
- Risk-based validation with automated recommendations
- Context-aware validation based on codebase patterns

Key Model Categories:
    Change Models: FileChange, PRDiff for representing file modifications
    Analysis Models: DiffAnalysisResult, SemanticAnalysisResult for change analysis
    Validation Models: ValidationResult, ValidationIssue for validation outcomes
    Impact Models: ChangeImpact, TestImpact, DocumentationImpact for scope analysis
    Context Models: CodebaseContext, PRAnalysisContext for analysis environment

Example:
    ```python
    from pr_validation_models import (
        FileChange, PRDiff, ValidationResult,
        ChangeType, RiskLevel, ChangeSeverity
    )

    # Create file change
    file_change = FileChange(
        filename="src/api/handlers.py",
        file_type=FileType.PYTHON,
        change_type=ChangeType.MODIFIED,
        additions=15,
        deletions=8,
        patch="@@ -42,7 +42,10 @@ def process_request(request):",
        before_content="def process_request(request):\n    return handle(request)",
        after_content="def process_request(request: Request) -> Response:\n    return handle(request)"
    )

    # Create PR diff
    pr_diff = PRDiff(
        base_sha="abc123",
        head_sha="def456",
        files_changed=[file_change],
        stats=DiffStats.from_files([file_change]),
        metadata={"pr_number": 123, "author": "developer"}
    )

    # Validation result
    result = ScriptValidationResult(
        validation_type="type_safety",
        passed=True,
        score=0.95,
        risk_level=RiskLevel.LOW,
        issues=[],
        recommendations=[],
        confidence=0.9
    )
    ```
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from .static_analysis import StaticAnalysisChangeType

# Alias for backward compatibility
ChangeType = StaticAnalysisChangeType


class FileType(Enum):
    """File types for specialized validation."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    MARKDOWN = "markdown"
    YAML = "yaml"
    JSON = "json"
    HTML = "html"
    CSS = "css"
    DOCKERFILE = "dockerfile"
    UNKNOWN = "unknown"


class RiskLevel(Enum):
    """Risk levels for validation results."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ChangeSeverity(Enum):
    """Severity levels for file changes."""

    MINOR = "MINOR"
    MODERATE = "MODERATE"
    MAJOR = "MAJOR"
    COMPLETE_REWRITE = "COMPLETE_REWRITE"
    SECURITY_ISSUE = "SECURITY_ISSUE"
    UNKNOWN = "UNKNOWN"


@dataclass
class DiffStats:
    """Statistics about a PR diff."""

    total_files: int
    total_additions: int
    total_deletions: int
    files_added: int
    files_deleted: int
    files_modified: int
    files_renamed: int

    @classmethod
    def from_files(cls, files_changed: list[FileChange]) -> DiffStats:
        """Create DiffStats from a list of file changes."""
        total_additions = sum(f.additions for f in files_changed)
        total_deletions = sum(f.deletions for f in files_changed)

        files_added = sum(1 for f in files_changed if f.change_type == ChangeType.ADDED)
        files_deleted = sum(1 for f in files_changed if f.change_type == ChangeType.DELETED)
        files_modified = sum(1 for f in files_changed if f.change_type == ChangeType.MODIFIED)
        files_renamed = sum(1 for f in files_changed if f.change_type == ChangeType.RENAMED)

        return cls(
            total_files=len(files_changed),
            total_additions=total_additions,
            total_deletions=total_deletions,
            files_added=files_added,
            files_deleted=files_deleted,
            files_modified=files_modified,
            files_renamed=files_renamed,
        )


@dataclass
class ValidationFileChange:
    """Represents changes to a single file in validation context."""

    filename: str
    file_type: FileType
    change_type: ChangeType
    additions: int
    deletions: int
    patch: str
    before_content: str | None = None
    after_content: str | None = None
    ast_before: ast.AST | None = None
    ast_after: ast.AST | None = None
    binary: bool = False

    @property
    def total_changes(self) -> int:
        """Total number of line changes."""
        return self.additions + self.deletions


# Alias for backward compatibility
FileChange = ValidationFileChange


@dataclass
class PRDiff:
    """Represents a complete PR diff with all changes."""

    base_sha: str
    head_sha: str
    files_changed: list[FileChange]
    stats: DiffStats
    metadata: dict[str, Any]

    @property
    def change_complexity(self) -> float:
        """Calculate overall change complexity."""
        if not self.files_changed:
            return 0.0

        total_changes = sum(f.total_changes for f in self.files_changed)
        return min(total_changes / 100.0, 10.0)  # Cap at 10.0


@dataclass
class ValidationIssue:
    """Represents a validation issue found during analysis."""

    type: str
    severity: str
    message: str
    file: str
    line: int | None = None
    column: int | None = None
    rule: str | None = None
    suggestion: str | None = None


@dataclass
class Recommendation:
    """Represents an actionable recommendation for update."""

    type: str
    priority: str
    description: str
    action: str
    file: str | None = None
    automated: bool = False


@dataclass
class APICompatibility:
    """Represents API compatibility information."""

    is_compatible: bool
    breaking_changes: list[str]
    deprecations: list[str]
    version_impact: str  # MAJOR, MINOR, PATCH


@dataclass
class TestImpact:
    """Represents impact on tests."""

    tests_affected: list[str]
    coverage_change: float
    new_tests_needed: list[str]
    obsolete_tests: list[str]


@dataclass
class DocumentationImpact:
    """Represents impact on documentation."""

    docs_affected: list[str]
    outdated_docs: list[str]
    new_docs_needed: list[str]
    doc_completeness_score: float


@dataclass
class ChangeImpact:
    """Represents the impact scope of changes."""

    affected_functions: list[str]
    affected_classes: list[str]
    dependency_impact: list[str]
    test_impact: TestImpact
    documentation_impact: DocumentationImpact
    api_compatibility: APICompatibility
    estimated_effort: str  # LOW, MEDIUM, HIGH


@dataclass
class ValidationResult:
    """Augmented validation result with change context."""

    validation_type: str
    passed: bool
    score: float
    risk_level: RiskLevel
    issues: list[ValidationIssue]
    recommendations: list[Recommendation]
    change_impact: ChangeImpact | None = None
    confidence: float = 1.0
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def critical_issues(self) -> list[ValidationIssue]:
        """Get only critical issues."""
        return [issue for issue in self.issues if issue.severity == "CRITICAL"]

    @property
    def high_priority_recommendations(self) -> list[Recommendation]:
        """Get high priority recommendations."""
        return [rec for rec in self.recommendations if rec.priority == "HIGH"]


@dataclass
class FileChangeAnalysis:
    """Analysis result for a single file change."""

    filename: str
    change_severity: ChangeSeverity
    change_patterns: list[str]
    risk_indicators: list[str]
    line_change_ratio: float
    content_similarity: float
    file_type: FileType

    @property
    def is_high_risk(self) -> bool:
        """Check if this change is high risk."""
        return (
            self.change_severity in [ChangeSeverity.COMPLETE_REWRITE, ChangeSeverity.SECURITY_ISSUE]
            or "DANGEROUS_LOGIC_CHANGES" in self.risk_indicators
            or "SECURITY_SENSITIVE_FILE_MODIFIED" in self.risk_indicators
        )


@dataclass
class DiffAnalysisResult:
    """Result of diff analysis."""

    file_analyses: list[FileChangeAnalysis]
    overall_patterns: list[str]
    risk_factors: list[str]
    change_complexity: float
    requires_careful_review: bool

    @property
    def high_risk_files(self) -> list[FileChangeAnalysis]:
        """Get files that are high risk."""
        return [analysis for analysis in self.file_analyses if analysis.is_high_risk]


@dataclass
class FunctionSignature:
    """Represents a function signature for comparison."""

    name: str
    args: list[str]
    defaults: list[str]
    varargs: str | None
    kwargs: str | None
    return_type: str | None
    decorators: list[str]
    is_public: bool
    lineno: int


@dataclass
class ClassDefinition:
    """Represents a class definition for comparison."""

    name: str
    bases: list[str]
    methods: dict[str, FunctionSignature]
    attributes: list[str]
    is_public: bool
    lineno: int


@dataclass
class BreakingChange:
    """Represents a breaking change in the API."""

    type: str
    severity: str
    description: str
    file_path: str
    affected_symbol: str
    recommendation: str
    line_number: int | None = None
    confidence: float = 1.0


@dataclass
class SemanticAnalysisResult:
    """Result of semantic analysis."""

    breaking_changes: list[BreakingChange]
    logic_safety_issues: list[ValidationIssue]
    api_surface_changes: dict[str, Any]
    complexity_changes: dict[str, float]

    @property
    def has_breaking_changes(self) -> bool:
        """Check if there are any breaking changes."""
        return len(self.breaking_changes) > 0

    @property
    def has_logic_safety_issues(self) -> bool:
        """Check if there are logic safety issues."""
        return len(self.logic_safety_issues) > 0


@dataclass
class ImpactAssessment:
    """Assessment of change impact across the codebase."""

    dependency_impacts: list[str]
    test_coverage_impact: TestImpact
    documentation_impact: DocumentationImpact
    performance_impact: dict[str, Any]
    security_impact: dict[str, Any]

    @property
    def overall_impact_score(self) -> float:
        """Calculate overall impact score."""
        score = 0.0
        if self.dependency_impacts:
            score += len(self.dependency_impacts) * 0.1
        if self.test_coverage_impact.coverage_change < 0:
            score += abs(self.test_coverage_impact.coverage_change) * 2.0
        if self.documentation_impact.outdated_docs:
            score += len(self.documentation_impact.outdated_docs) * 0.05
        return min(score, 10.0)


@dataclass
class CodebaseContext:
    """Context about the codebase for analysis."""

    total_files: int
    total_lines: int
    main_languages: list[str]
    test_framework: str | None
    documentation_format: str | None
    dependencies: list[str]
    architecture_patterns: list[str]


@dataclass
class PRAnalysisContext:
    """Context for running analysis."""

    pr_diff: PRDiff
    codebase_context: CodebaseContext
    diff_analysis: DiffAnalysisResult | None = None
    semantic_analysis: SemanticAnalysisResult | None = None
    impact_assessment: ImpactAssessment | None = None
    validation_config: dict[str, Any] = field(default_factory=dict)


# Rebuild models to ensure proper forward reference resolution
# For Pydantic v2, use model_rebuild if available, otherwise skip
if hasattr(FunctionSignature, "model_rebuild"):
    FunctionSignature.model_rebuild()
if hasattr(FileChange, "model_rebuild"):
    FileChange.model_rebuild()
