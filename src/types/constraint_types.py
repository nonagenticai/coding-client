"""
Constraint types using Pydantic's Annotated types for validation.

These types provide runtime validation and constraints for various
data types used throughout the system.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, Field


def validate_container_name(name: str) -> str:
    """Validate Docker container naming constraints."""
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$", name):
        raise ValueError("Container name must match Docker naming rules")
    if len(name) > 63:
        raise ValueError("Container name too long (max 63 characters)")
    return name


def validate_github_repo_url(url: str) -> str:
    """Validate GitHub repository URL format."""
    github_pattern = r"^https://github\.com/[a-zA-Z0-9\-_\.]+/[a-zA-Z0-9\-_\.]+(?:\.git)?/?$"
    if not re.match(github_pattern, url):
        raise ValueError("Invalid GitHub repository URL format")
    return url


def validate_code_content(content: str) -> str:
    """Validate code content size and format."""
    if len(content) > 1024 * 1024:  # 1MB limit
        raise ValueError("Code content too large (max 1MB)")
    if not content.strip():
        raise ValueError("Code content cannot be empty")
    return content


def validate_absolute_path(path: str) -> str:
    """Validate absolute file path."""
    if not path.startswith("/") and not (len(path) > 2 and path[1] == ":"):
        raise ValueError("Path must be absolute")
    return path


def validate_relative_path(path: str) -> str:
    """Validate relative file path."""
    if path.startswith("/") or (len(path) > 2 and path[1] == ":"):
        raise ValueError("Path must be relative")
    if ".." in path:
        raise ValueError("Path cannot contain '..' segments")
    return path


def validate_user_identifier(user_id: str) -> str:
    """Validate user identifier format."""
    if not re.match(r"^[a-zA-Z0-9_-]+$", user_id):
        raise ValueError("User ID must contain only alphanumeric, underscore, and dash characters")
    if len(user_id) < 3 or len(user_id) > 50:
        raise ValueError("User ID must be between 3 and 50 characters")
    return user_id


def validate_request_id(req_id: str) -> str:
    """Validate request ID format."""
    if not req_id.startswith("req_"):
        raise ValueError("Request ID must start with 'req_'")
    if len(req_id) > 100:
        raise ValueError("Request ID too long (max 100 characters)")
    return req_id


def validate_analysis_id(analysis_id: str) -> str:
    """Validate analysis ID format."""
    if not analysis_id.startswith("anal_"):
        raise ValueError("Analysis ID must start with 'anal_'")
    if len(analysis_id) > 100:
        raise ValueError("Analysis ID too long (max 100 characters)")
    return analysis_id


def validate_future_timestamp(timestamp: datetime) -> datetime:
    """Validate that timestamp is in the future."""
    if timestamp <= datetime.now(UTC):
        raise ValueError("Timestamp must be in the future")
    return timestamp


# Container naming constraint (Docker compatible)
ContainerName = Annotated[
    str,
    Field(min_length=1, max_length=63, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$"),
    AfterValidator(validate_container_name),
]

# GitHub repository URL constraint
GitHubRepoUrl = Annotated[
    str, Field(min_length=1, max_length=500), AfterValidator(validate_github_repo_url)
]

# Code content constraint
CodeContent = Annotated[
    str,
    Field(min_length=1, max_length=1024 * 1024),  # 1MB limit
    AfterValidator(validate_code_content),
]

# Memory constraints (in MB)
MemoryMB = Annotated[
    int,
    Field(ge=64, le=32768),  # 64MB to 32GB
]

# CPU constraints (in cores)
CPUCores = Annotated[
    float,
    Field(ge=0.1, le=16.0),  # 0.1 to 16 cores
]

# Timeout constraints (in seconds)
TimeoutSeconds = Annotated[
    int,
    Field(ge=1, le=3600),  # 1 second to 1 hour
]

# File path constraints
AbsolutePath = Annotated[
    str, Field(min_length=1, max_length=4096), AfterValidator(validate_absolute_path)
]

RelativePath = Annotated[
    str, Field(min_length=1, max_length=4096), AfterValidator(validate_relative_path)
]

# User identifier constraint
UserIdentifier = Annotated[
    str,
    Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$"),
    AfterValidator(validate_user_identifier),
]

# Request ID constraint
RequestID = Annotated[
    str,
    Field(min_length=5, max_length=100, pattern=r"^req_.*"),
    AfterValidator(validate_request_id),
]

# Analysis ID constraint
AnalysisID = Annotated[
    str,
    Field(min_length=6, max_length=100, pattern=r"^anal_.*"),
    AfterValidator(validate_analysis_id),
]

# Code snippet constraint (smaller than full code)
CodeSnippet = Annotated[
    str,
    Field(min_length=1, max_length=10240),  # 10KB limit for snippets
]

# Port number constraint
PortNumber = Annotated[
    int,
    Field(ge=1, le=65535),
]

# Percentage constraint
Percentage = Annotated[
    float,
    Field(ge=0.0, le=100.0),
]

# Score constraint (0-10)
Score = Annotated[
    float,
    Field(ge=0.0, le=10.0),
]

# Confidence constraint (0-1)
Confidence = Annotated[
    float,
    Field(ge=0.0, le=1.0),
]

# Timestamp constraints
ValidTimestamp = Annotated[datetime, Field(description="Valid timestamp (past or present)")]

FutureTimestamp = Annotated[
    datetime,
    Field(description="Future timestamp"),
    AfterValidator(validate_future_timestamp),
]

# File size constraints
FileSizeBytes = Annotated[
    int,
    Field(ge=0, le=100 * 1024 * 1024),  # 0 to 100MB
]

# Line number constraint
LineNumber = Annotated[
    int,
    Field(ge=1, le=1000000),  # Line 1 to 1 million
]

# Column number constraint
ColumnNumber = Annotated[
    int,
    Field(ge=1, le=1000),  # Column 1 to 1000
]

# =============================================================================
# SafeString Types for Schemathesis Contract Test Compatibility
# =============================================================================
# These patterns block dangerous control characters while allowing:
# - All printable ASCII (0x20-0x7E)
# - Tab (0x09), Newline (0x0A), Carriage Return (0x0D)
# - All Unicode characters (0x80+)
#
# Blocked characters: NULL (0x00), 0x01-0x08, VT (0x0B), FF (0x0C), 0x0E-0x1F, DEL (0x7F)
# This matches the validation in src/app/middleware/input_validator.py
# =============================================================================

# Pattern that blocks dangerous control characters
SAFE_STRING_PATTERN = r"^[^\x00-\x08\x0B\x0C\x0E-\x1F\x7F]*$"

# Basic safe string - no length constraints
SafeString = Annotated[
    str,
    Field(pattern=SAFE_STRING_PATTERN),
]

# Safe string for identifiers and short values (container names, IDs, etc.)
SafeStringShort = Annotated[
    str,
    Field(min_length=1, max_length=256, pattern=SAFE_STRING_PATTERN),
]

# Safe string for medium-length content (messages, descriptions, titles)
SafeStringMedium = Annotated[
    str,
    Field(min_length=1, max_length=1000, pattern=SAFE_STRING_PATTERN),
]

# Safe string for longer content (error messages, recommendations)
SafeStringLong = Annotated[
    str,
    Field(min_length=1, max_length=10000, pattern=SAFE_STRING_PATTERN),
]

# Safe string for code content (file paths, code snippets, stdout/stderr)
SafeCodeString = Annotated[
    str,
    Field(max_length=50000, pattern=SAFE_STRING_PATTERN),
]

# Optional safe string variants
SafeStringOptional = Annotated[
    str,
    Field(pattern=SAFE_STRING_PATTERN),
]

SafeStringShortOptional = Annotated[
    str,
    Field(max_length=256, pattern=SAFE_STRING_PATTERN),
]

SafeStringMediumOptional = Annotated[
    str,
    Field(max_length=1000, pattern=SAFE_STRING_PATTERN),
]
