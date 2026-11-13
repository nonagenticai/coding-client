"""Tests for coding_client.llm.responses."""

from __future__ import annotations

import pytest
from coding_client.llm.responses import (
    Bottleneck,
    CodeQualityAnalysisResponse,
    PerformanceAnalysisResponse,
    QualityIssue,
    TestFailureAnalysisResponse,
)
from pydantic import ValidationError


def test_test_failure_valid():
    resp = TestFailureAnalysisResponse.model_validate(
        {
            "root_cause": "assertion off-by-one",
            "suggested_fix": "use len(items) - 1",
            "confidence": 0.8,
            "category": "assertion",
        }
    )
    assert resp.confidence == 0.8
    assert resp.category == "assertion"


def test_test_failure_extra_forbidden():
    with pytest.raises(ValidationError):
        TestFailureAnalysisResponse.model_validate(
            {
                "root_cause": "x",
                "suggested_fix": "y",
                "confidence": 0.5,
                "category": "assertion",
                "unexpected": "boom",
            }
        )


def test_test_failure_confidence_bounds():
    with pytest.raises(ValidationError):
        TestFailureAnalysisResponse.model_validate(
            {
                "root_cause": "x",
                "suggested_fix": "y",
                "confidence": 1.5,
                "category": "assertion",
            }
        )


def test_test_failure_category_literal():
    with pytest.raises(ValidationError):
        TestFailureAnalysisResponse.model_validate(
            {
                "root_cause": "x",
                "suggested_fix": "y",
                "confidence": 0.5,
                "category": "unknown_category",
            }
        )


def test_quality_response_empty_ok():
    resp = CodeQualityAnalysisResponse.model_validate({"issues": []})
    assert resp.issues == []


def test_quality_response_with_issue():
    resp = CodeQualityAnalysisResponse.model_validate(
        {
            "issues": [
                {
                    "severity": "warning",
                    "category": "maintainability",
                    "description": "long function",
                    "suggested_refactor": "split into helpers",
                }
            ]
        }
    )
    assert len(resp.issues) == 1
    assert isinstance(resp.issues[0], QualityIssue)
    assert resp.issues[0].severity == "warning"


def test_quality_issue_severity_literal():
    with pytest.raises(ValidationError):
        QualityIssue.model_validate({"severity": "blocker", "category": "x", "description": "y"})


def test_performance_response():
    resp = PerformanceAnalysisResponse.model_validate(
        {
            "bottlenecks": [
                {
                    "location": "foo.py:42",
                    "impact": "high",
                    "description": "n+1 query",
                    "suggested_optimisation": "batch fetch",
                }
            ]
        }
    )
    assert isinstance(resp.bottlenecks[0], Bottleneck)
    assert resp.bottlenecks[0].impact == "high"


def test_performance_extra_forbidden():
    with pytest.raises(ValidationError):
        Bottleneck.model_validate(
            {
                "location": "f.py",
                "impact": "low",
                "description": "x",
                "suggested_optimisation": "y",
                "rogue": True,
            }
        )
