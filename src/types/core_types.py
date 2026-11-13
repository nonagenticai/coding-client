"""
Core Literal types for type safety in critical system paths.

These types provide compile-time and runtime type safety for key system
constants and enumerations, reducing runtime errors and improving code clarity.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

# Language Support - based on subagent analysis
SupportedLanguage = Literal[
    "python", "javascript", "typescript", "java", "rust", "go", "csharp", "cpp"
]

# Execution Modes - based on timeout_manager.py analysis
ExecutionMode = Literal["validate", "execute", "test", "analyze", "quality_check", "security_scan"]

# Container States - based on test_orchestrator.py analysis
ContainerState = Literal[
    "creating", "running", "stopped", "error", "removing", "paused", "restarting"
]

# Analysis States - for analysis pipeline tracking
AnalysisState = Literal["queued", "processing", "completed", "failed", "cancelled", "timeout"]

# Response States - for API responses
ResponseState = Literal["success", "error", "pending", "timeout", "unauthorized", "forbidden"]

# Validation Results - for validation outcomes
ValidationResult = Literal["valid", "invalid", "warning", "error", "timeout", "pending"]

# Quality Levels - for quality assessment
QualityLevel = Literal["low", "medium", "high", "critical"]

# Health States - for system health monitoring
HealthState = Literal["healthy", "unhealthy", "unknown", "degraded", "critical", "maintenance"]

# Security Levels - for security classification
SecurityLevel = Literal["low", "medium", "high", "critical"]

# Test Types - for test execution
TestType = Literal["unit", "integration", "functional", "performance", "security", "coverage"]

# Test States - for test execution tracking
TestState = Literal["pending", "running", "passed", "failed", "skipped", "timeout", "error"]

# Error Categories - for error classification
ErrorCategory = Literal[
    "timeout",
    "execution_error",
    "validation_error",
    "type_error",
    "permission_error",
    "network_error",
    "system_error",
]

# Exit Codes - for process exit codes
ExitCode = Literal[0, 1, 124]  # Success, Error, Timeout

# Database States - for database operations
DatabaseState = Literal["connected", "disconnected", "error", "readonly", "locked"]

# Transaction States - for transaction management
TransactionState = Literal["idle", "active", "committed", "rolled_back", "failed"]

# GitHub Event Types - for webhook handling
GitHubEventType = Literal[
    "push",
    "pull_request",
    "issues",
    "issue_comment",
    "pull_request_review",
    "pull_request_review_comment",
    "create",
    "delete",
    "release",
]


# GitHub Event Types as Enum - for webhook handler compatibility
class GitHubEventTypeEnum(StrEnum):
    """GitHub webhook event types as enum for easier handling."""

    PUSH = "push"
    PULL_REQUEST = "pull_request"
    ISSUES = "issues"
    ISSUE_COMMENT = "issue_comment"
    PULL_REQUEST_REVIEW = "pull_request_review"
    PULL_REQUEST_REVIEW_COMMENT = "pull_request_review_comment"
    CREATE = "create"
    DELETE = "delete"
    RELEASE = "release"


# PR States - for pull request management
PRState = Literal["open", "closed", "merged", "draft", "review_required"]

# Analysis Types - for code analysis
AnalysisType = Literal["syntax", "semantic", "security", "performance", "quality", "architecture"]

# File Operation Types
FileOperationType = Literal["read", "write", "append", "delete", "copy", "move", "create"]

# Network Operation Types
NetworkOperationType = Literal["get", "post", "put", "delete", "patch", "options", "head"]

# Cache Operation Types
CacheOperationType = Literal["get", "set", "delete", "clear", "expire", "exists"]
