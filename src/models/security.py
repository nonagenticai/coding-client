"""Security-specific Pydantic models for code security analysis and validation.

This module provides comprehensive data models for security analysis operations,
including code vulnerability detection, security violation reporting, and
security-aware code validation. The models support multi-level security
assessment and provide structured security analysis results.

The security analysis system enables:
- Code vulnerability detection with severity assessment
- Security violation reporting with remediation suggestions
- Multi-level security validation (LOW, MEDIUM, HIGH, CRITICAL)
- Context-aware security analysis with configurable rules
- Integration with security scanning tools and methodologies

Key Model Categories:
    Enumeration Models: SecurityLevel for security level classification
    Violation Models: SecurityViolation for detected security issues
    Request Models: SecurityValidationRequest, SecurityScanRequest, SecurityReportRequest
    Response Models: SecurityValidationResult, VulnerabilityScanResult

Security Features:
    - Pattern-based vulnerability detection
    - Severity-based issue classification
    - Remediation suggestion generation
    - Context-aware security analysis
    - Configurable security validation levels

Example:
    ```python
    from security_models import (
        SecurityLevel, SecurityViolation,
        SecurityValidationRequest, SecurityValidationResult
    )

    # Create security validation request
    request = SecurityValidationRequest(
        code='import os\\nos.system("rm -rf /")',
        language="python",
        security_level=SecurityLevel.HIGH,
        context={"environment": "production"}
    )

    # Security violation detection
    violation = SecurityViolation(
        type="command_injection",
        severity=SecurityLevel.CRITICAL,
        line_number=2,
        pattern_matched="os.system",
        description="Dangerous system command execution detected",
        suggested_fix="Use subprocess.run with shell=False instead"
    )

    # Security validation result
    result = SecurityValidationResult(
        is_safe=False,
        violations=[violation],
        risk_score=95.0,
        sandbox_config={"network_access": False, "file_system": "read_only"}
    )
    ```
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SecurityLevel(StrEnum):
    """Enumeration of security levels for code validation and risk assessment.

    Defines the security validation levels that determine the depth and strictness
    of security analysis performed on code. Each level applies different security
    rules and has different performance characteristics.

    Attributes:
        LOW: Basic security checks with minimal performance impact.
            Suitable for development environments and low-risk code.
        MEDIUM: Standard security validation with balanced performance.
            Appropriate for most production code and regular workflows.
        HIGH: Comprehensive security analysis with thorough validation.
            Recommended for security-sensitive applications and critical systems.
        CRITICAL: Maximum security scrutiny with intensive analysis.
            Required for high-security environments and critical infrastructure.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityViolation(BaseModel):
    """Model representing a security violation detected in code analysis."""

    type: str = Field(..., description="Type of security violation")
    severity: SecurityLevel = Field(..., description="Severity level")
    line_number: int | None = Field(None, description="Line number where violation occurs")
    pattern_matched: str = Field(..., description="Pattern that triggered the violation")
    description: str = Field(..., description="Human-readable description")
    suggested_fix: str | None = Field(None, description="Suggested remediation")


class SecurityValidationRequest(BaseModel):
    """Request model for security validation of code snippets."""

    code: str = Field(..., description="Code to validate")
    language: str = Field(..., description="Programming language")
    security_level: SecurityLevel = Field(
        SecurityLevel.MEDIUM, description="Required security level"
    )
    context: dict[str, Any] | None = Field(None, description="Additional context for validation")
    container_name: str | None = Field(
        None, description="Optional container name (accepted but not used)"
    )


class SecurityValidationResult(BaseModel):
    """Result model for security validation outcomes."""

    is_safe: bool = Field(..., description="Whether code passes security validation")
    violations: list[SecurityViolation] = Field(default_factory=list)
    risk_score: float = Field(..., ge=0, le=100, description="Overall risk score")
    sandbox_config: dict[str, Any] | None = Field(
        None, description="Recommended sandbox configuration"
    )


class SecurityScanRequest(BaseModel):
    """Request model for initiating a security scan on a container."""

    container_name: str = Field(..., description="Name of the container to scan")
    scan_type: str | None = Field("full", description="Type of security scan to perform")
    include_dependencies: bool = Field(True, description="Whether to include dependency scanning")


class SecurityReportRequest(BaseModel):
    """Request model for generating a security report for a container."""

    container_name: str = Field(..., description="Name of the container for security report")
    format: str = Field("json", description="Output format for the report")


class VulnerabilityScanResult(BaseModel):
    """Result model for vulnerability scanning operations."""

    container_name: str = Field(..., description="Name of the scanned container")
    vulnerabilities: list[dict] = Field(
        default_factory=list, description="List of detected vulnerabilities"
    )
    scan_timestamp: datetime = Field(..., description="Timestamp when the scan was completed")


class OSVPackageInfo(BaseModel):
    """Model representing package information for OSV.dev queries."""

    name: str = Field(..., description="Package name")
    ecosystem: str = Field(..., description="Package ecosystem")


class OSVVulnerability(BaseModel):
    """Model representing an OSV.dev vulnerability."""

    id: str = Field(..., description="Vulnerability identifier (e.g., GHSA-xxxx)")
    summary: str = Field(..., description="Vulnerability summary")
    details: str | None = Field(None, description="Detailed description")
    severity: str | None = Field(None, description="Severity level")
    affected_versions: list[str] = Field(default_factory=list, description="Affected versions")
    fixed_versions: list[str] | None = Field(None, description="Versions where issue is fixed")
    cve_ids: list[str] = Field(default_factory=list, description="Associated CVE IDs")
    references: list[str] = Field(default_factory=list, description="Reference URLs")
    published_date: str | None = Field(None, description="Publication date")
    package_name: str = Field(..., description="Affected package name")
    ecosystem: str = Field(..., description="Package ecosystem")


class PackageInfo(BaseModel):
    """Model representing package information for batch queries."""

    name: str = Field(..., description="Package name")
    version: str = Field(..., description="Package version")
    ecosystem: str = Field(..., description="Package ecosystem")
