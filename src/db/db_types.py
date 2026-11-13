"""Type definitions for database operations.

This module provides TypedDict classes and type aliases for better type safety
in database operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict


class NodeProperties(TypedDict, total=False):
    """Properties stored for code graph nodes."""

    name: str
    qualified_name: str
    path: str
    file_path: str
    docstring: str | None
    complexity: int | None
    return_type: dict[str, Any] | None
    parameter_types: list[dict[str, Any]]
    properties: dict[str, Any]
    metadata: dict[str, Any]
    content_hash: str


class EdgeProperties(TypedDict, total=False):
    """Properties stored for code graph edges."""

    weight: float
    context: str | None
    location_file: str | None
    location_line: int | None
    location_column: int | None


class NodeRecord(TypedDict):
    """Complete database record for a node."""

    id: str
    type: str
    properties: str  # JSON-serialized NodeProperties
    created_at: datetime
    updated_at: datetime
    content_hash: str
    file_size: int | None
    # Multi-language fields
    language: str
    file_path: str | None
    line_number: int | None
    column_start: int | None
    column_end: int | None
    visibility: str | None
    is_static: bool
    is_abstract: bool
    is_final: bool
    is_async: bool
    signature: str | None
    docstring: str | None


class EdgeRecord(TypedDict):
    """Complete database record for an edge."""

    id: int
    source: str
    target: str
    relationship: str
    properties: str | None  # JSON-serialized EdgeProperties
    weight: float
    created_at: datetime
    context: str | None
    location_file: str | None
    location_line: int | None
    location_column: int | None


class CoreLanguageStats(TypedDict):
    """Language statistics record."""

    language: str
    file_path: str
    entity_count: int
    relationship_count: int
    lines_of_code: int
    complexity_score: float
    last_analyzed: datetime


class LanguageSummary(TypedDict):
    """Aggregated language statistics."""

    file_count: int
    total_entities: int
    total_relationships: int
    total_lines: int
    avg_complexity: float


class SchemaVersion(TypedDict):
    """Schema version record."""

    version: int
    description: str
    applied_at: datetime


class AnalysisSession(TypedDict):
    """Analysis session tracking record."""

    id: str
    started_at: datetime
    completed_at: datetime | None
    languages: str  # JSON array
    files_processed: int
    files_failed: int
    total_entities: int
    total_relationships: int
    status: str  # 'running', 'completed', 'failed'
    error_message: str | None
