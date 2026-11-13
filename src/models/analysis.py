"""Analysis models for deep code analysis and improvement generation.

This module provides Pydantic models for the analysis API endpoints, supporting
deep static code analysis, bug hunting, and automated code improvement workflows.
The models facilitate comprehensive code quality assessment and remediation
through AI-powered analysis and GitHub integration.

The analysis system supports:
- Deep static analysis with multi-dimensional quality assessment
- Bug hunting from error logs with automated remediation
- Code improvement suggestions with confidence scoring
- GitHub integration for automated PR creation
- Validation of proposed code changes
- Comprehensive reporting with actionable insights

Key Model Categories:
    Request Models: DeepAnalysisRequest, BugHuntingRequest, ImprovementRequest
    Response Models: DeepAnalysisResponse, BugHuntingResponse for analysis results
    Data Models: ImprovementItem, CodeValidationRequest for change representation
    Integration Models: GitHub token and repository handling for PR creation

Analysis Types:
    - Security vulnerability detection
    - Performance issue identification
    - Code complexity analysis
    - Code smell detection
    - Architectural analysis
    - Documentation quality assessment
    - Bug risk analysis

Example:
    ```python
    from analysis_models import DeepAnalysisRequest, BugHuntingRequest, ImprovementItem

    # Deep analysis request
    analysis_request = DeepAnalysisRequest(
        include_security=True,
        include_performance=True,
        include_complexity=True,
        include_code_smells=True,
        include_architecture=True,
        include_documentation=True,
        include_bug_risks=True
    )

    # Bug hunting request
    bug_request = BugHuntingRequest(
        error_logs="Traceback: ImportError: No module named 'requests'",
        create_pr=True,
        github_repo="owner/repository",
        GITHUB_ACCESS_TOKEN="ghp_token"
    )

    # Improvement item
    improvement = ImprovementItem(
        file_path="src/main.py",
        fixed_code=(
            "import requests\\n\\ndef fetch_data():\\n    "
            "response = requests.get('https://api.example.com/data')\\n    return response.json()"
        ),
        original_code="def fetch_data():\\n    # TODO: implement data fetching\\n    pass",
        description="Implement data fetching functionality",
        confidence=0.9,
        fix_type="implementation"
    )
    ```
"""

from __future__ import annotations

import logging
from typing import TypedDict

from pydantic import BaseModel, Field, model_validator

# Configure logging for analysis models
logger = logging.getLogger(__name__)


class BugHuntingContextDict(TypedDict, total=False):
    """Type definition for bug hunting context information.

    This dictionary structure provides context for bug hunting analysis,
    including repository metadata, environment details, and execution context.
    """

    container_name: str
    repository_path: str
    branch: str
    commit_hash: str
    environment: str
    runtime_version: str
    error_timestamp: str
    user_id: str
    session_id: str
    error_type: str
    stack_trace: str
    affected_files: list[str]
    recent_changes: list[str]
    system_info: dict[str, str]


class AnalysisMetricsDict(TypedDict):
    """Type definition for analysis metrics data.

    Comprehensive metrics for code quality assessment including
    maintainability, security, performance, and coverage indicators.
    """

    lines_of_code: int
    cyclomatic_complexity: float
    maintainability_index: float
    test_coverage: float
    code_duplication: float
    security_score: float
    performance_score: float
    documentation_coverage: float
    technical_debt_ratio: float
    complexity_violations: int
    security_vulnerabilities: int
    performance_issues: int
    code_smells: int
    test_failures: int


class AnalysisIssueDict(TypedDict):
    """Type definition for individual analysis issues.

    Structured representation of code quality issues with
    location, severity, and remediation information.
    """

    id: str
    severity: str  # "critical", "high", "medium", "low"
    type: str  # "security", "performance", "complexity", "maintainability"
    category: str
    file_path: str
    line_number: int
    column_number: int
    message: str
    description: str
    fix_suggestion: str
    confidence: float
    rule_id: str
    tool_name: str
    impact: str
    effort: str


class ErrorDetailDict(TypedDict):
    """Type definition for error analysis details.

    Structured representation of parsed error information
    with context and classification data.
    """

    error_id: str
    error_type: str
    error_message: str
    stack_trace: str
    file_path: str
    line_number: int
    function_name: str
    error_category: str
    severity: str
    timestamp: str
    frequency: int
    impact_score: float
    suggested_fix: str
    related_errors: list[str]


class FixDetailDict(TypedDict):
    """Type definition for bug fix details.

    Structured representation of proposed fixes with
    implementation details and risk assessment.
    """

    fix_id: str
    fix_type: str
    file_path: str
    line_number: int
    original_code: str
    fixed_code: str
    description: str
    confidence: float
    risk_level: str
    test_impact: str
    dependencies: list[str]
    validation_steps: list[str]
    rollback_plan: str


class PullRequestDict(TypedDict):
    """Type definition for pull request information.

    Structured representation of GitHub pull request data
    with creation and status details.
    """

    pr_number: int
    pr_url: str
    pr_title: str
    pr_description: str
    branch_name: str
    commit_hash: str
    status: str
    created_at: str
    updated_at: str
    mergeable: bool
    conflicts: list[str]
    checks_passed: bool
    review_required: bool
    files_changed: list[str]


class DeepAnalysisRequest(BaseModel):
    """Request for deep static code analysis."""

    include_security: bool = Field(True, description="Include security vulnerability analysis")
    include_performance: bool = Field(True, description="Include performance issue analysis")
    include_complexity: bool = Field(True, description="Include code complexity analysis")
    include_code_smells: bool = Field(True, description="Include code smell detection")
    include_architecture: bool = Field(True, description="Include architectural analysis")
    include_documentation: bool = Field(True, description="Include documentation quality analysis")
    include_bug_risks: bool = Field(True, description="Include potential bug risk analysis")


class BugHuntingRequest(BaseModel):
    """Request for bug hunting from error logs."""

    error_logs: str | None = Field(
        "",
        description=(
            "Console logs, error output, or deep analysis results to analyze. "
            "If empty, will scan codebase for potential issues."
        ),
    )
    error_logs_base64: str | None = Field(
        None,
        description="Base64-encoded console logs or error output. Decoded before analysis.",
    )
    context: BugHuntingContextDict | None = Field(
        None, description="Additional context information for bug hunting"
    )
    create_pr: bool = Field(False, description="Whether to create a pull request with resolves")
    github_repo: str | None = Field(
        None, description="GitHub repository (owner/repo) for PR creation"
    )
    GITHUB_ACCESS_TOKEN: str | None = Field(None, description="GitHub token for PR creation")


class DeepAnalysisResponse(BaseModel):
    """Response for deep static code analysis."""

    overall_score: float = Field(description="Overall code quality score (0-10)")
    total_issues: int = Field(description="Total number of issues found")
    issues_by_severity: dict[str, int] = Field(description="Issues grouped by severity")
    issues_by_type: dict[str, int] = Field(description="Issues grouped by type")
    metrics: AnalysisMetricsDict = Field(description="Comprehensive codebase quality metrics")
    recommendations: list[str] = Field(description="High-level recommendations")
    issues: list[AnalysisIssueDict] = Field(description="Detailed list of code quality issues")
    analysis_time: float = Field(description="Time taken for analysis (seconds)")


class BugHuntingResponse(BaseModel):
    """Response for bug hunting analysis."""

    errors_found: int = Field(description="Number of errors identified")
    fixes_generated: int = Field(description="Number of resolves generated")
    root_cause_analysis: str = Field(description="Analysis of root causes")
    fix_summary: str = Field(description="Summary of proposed resolves")
    estimated_effort: str = Field(description="Estimated effort to implement resolves")
    risk_assessment: str = Field(description="Risk assessment of proposed resolves")
    errors: list[ErrorDetailDict] = Field(description="Parsed error details with context")
    resolves: list[FixDetailDict] = Field(description="Generated fix proposals")
    pull_request: PullRequestDict | None = Field(
        None, description="Pull request information if created"
    )
    analysis_time: float = Field(description="Time taken for analysis (seconds)")


class ImprovementItem(BaseModel):
    """Individual update item model."""

    file_path: str = Field(..., description="Path to the file to be updated", min_length=1)
    fixed_code: str | None = Field(None, description="The updated code content")
    code: str | None = Field(None, description="Alternative field name for code content")
    original_code: str | None = Field(None, description="The original code content")
    line_number: int | None = Field(None, description="Line number of the change")
    description: str | None = Field(None, description="Description of the update")
    confidence: float | None = Field(0.8, description="Confidence score for the update")
    fix_type: str | None = Field("augmentation", description="Type of resolve/update")

    @model_validator(mode="after")
    def check_code_or_fixed_code(self) -> ImprovementItem:
        """Validate that at least one of fixed_code or code is provided in the model.

        Raises:
            ValueError: If neither fixed_code nor code is present.
        """
        logger.debug(f"Validating ImprovementItem for file: {self.file_path}")
        if not self.fixed_code and not self.code:
            logger.error(f"Missing code content for improvement item: {self.file_path}")
            raise ValueError("At least one of fixed_code or code must be provided")
        # Log validation success
        logger.debug(f"ImprovementItem validation successful for {self.file_path}")
        return self


class ImprovementRequest(BaseModel):
    """Request model for creating update PR."""

    github_repo: str = Field(..., description="GitHub repository (owner/repo)", min_length=1)
    GITHUB_ACCESS_TOKEN: str = Field(..., description="GitHub token for API access", min_length=1)
    updates: list[ImprovementItem] = Field(..., description="List of code updates", min_length=1)
    pr_title: str | None = Field(None, description="Pull request title")
    pr_description: str | None = Field(None, description="Pull request description")


class CodeValidationRequest(BaseModel):
    """Request model for validating proposed code changes."""

    code: str = Field(..., description="The proposed code changes", min_length=1)
    filename: str = Field(..., description="The filename of the code", min_length=1)
    relative_path: str | None = Field(None, description="The relative path to the original file")
    language: str = Field(..., description="The programming language of the code", min_length=1)
    author: str = Field(..., description="The author of the code", min_length=1)
    description: str = Field(..., description="A brief description of the changes", min_length=1)
