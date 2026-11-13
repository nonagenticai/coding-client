"""Pydantic v2 response models for coding-* LLM agents.

All models use ``extra="forbid"`` so pydantic-ai surfaces schema mismatches
cleanly to inference-router (which then triggers fallback to the next
provider in the chain).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Test failure analysis (used by coding-testing).
# ---------------------------------------------------------------------------


class TestFailureAnalysisResponse(BaseModel):
    """Structured analysis of a single failed test."""

    __test__ = False  # Pytest: don't try to collect — class name starts with "Test".

    model_config = ConfigDict(extra="forbid")

    root_cause: str = Field(..., description="Concise root-cause explanation.")
    suggested_fix: str = Field(..., description="Concrete, actionable fix.")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence in the diagnosis (0..1).",
    )
    category: Literal[
        "assertion",
        "timeout",
        "import",
        "syntax",
        "environment",
        "flaky",
        "other",
    ] = Field(..., description="Failure category for routing/aggregation.")


# ---------------------------------------------------------------------------
# Code quality analysis (used by coding-ai).
# ---------------------------------------------------------------------------


class QualityIssue(BaseModel):
    """One code-quality finding."""

    model_config = ConfigDict(extra="forbid")

    severity: Literal["info", "warning", "error", "critical"]
    category: str = Field(..., description="Issue category, e.g. 'maintainability'.")
    description: str = Field(..., description="Human-readable issue description.")
    suggested_refactor: str | None = Field(
        default=None,
        description="Optional suggested refactor, when actionable.",
    )


class CodeQualityAnalysisResponse(BaseModel):
    """Structured code-quality analysis output."""

    model_config = ConfigDict(extra="forbid")

    issues: list[QualityIssue] = Field(
        default_factory=list,
        description="List of identified quality issues (may be empty).",
    )


# ---------------------------------------------------------------------------
# Performance analysis (used by coding-containers / coding-ai).
# ---------------------------------------------------------------------------


class Bottleneck(BaseModel):
    """One performance bottleneck."""

    model_config = ConfigDict(extra="forbid")

    location: str = Field(..., description="File path / function / span identifier.")
    impact: Literal["low", "medium", "high"]
    description: str = Field(..., description="Why this is a bottleneck.")
    suggested_optimisation: str = Field(
        ...,
        description="Concrete optimisation suggestion.",
    )


class PerformanceAnalysisResponse(BaseModel):
    """Structured performance-analysis output."""

    model_config = ConfigDict(extra="forbid")

    bottlenecks: list[Bottleneck] = Field(
        default_factory=list,
        description="Identified bottlenecks (may be empty).",
    )
