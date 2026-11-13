"""Tests for coding_client.models.architecture module."""

from __future__ import annotations

from pathlib import Path

import pytest
from coding_client.models.architecture import (
    ArchitecturalMetric,
    ArchitectureGraphMetrics,
    ArchitectureGraphResponse,
    ArchitectureJobRequest,
    ArchitectureRuntimeEdge,
    CodeGraphData,
    Component,
    ComponentExtractionStats,
    DependencyRiskSummary,
    DetectedPattern,
    GraphEdge,
    GraphNode,
    HotspotPrediction,
    Layer,
    LayerViolation,
    ModelMigrationTools,
    QualityGateCheck,
    QualityGateResult,
    QualityReport,
    RepoConfig,
    RuntimeData,
    Vulnerability,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------


class TestComponent:
    """Tests for Component model."""

    def test_create_valid(self):
        c = Component(id="core", name="Core", files=["src/core.py"])
        assert c.id == "core"
        assert c.name == "Core"
        assert c.files == ["src/core.py"]
        assert c.dependencies == []
        assert c.layer is None
        assert c.tags == []

    def test_invalid_id_chars_rejected(self):
        with pytest.raises(ValidationError, match="alphanumeric"):
            Component(id="core module!", name="Core", files=["a.py"])

    def test_id_with_hyphens_and_underscores(self):
        c = Component(id="my-core_module", name="Core", files=["a.py"])
        assert c.id == "my-core_module"

    def test_empty_files_rejected(self):
        with pytest.raises(ValidationError, match="at least one file"):
            Component(id="core", name="Core", files=[])

    def test_self_referencing_dependency_rejected(self):
        with pytest.raises(ValidationError, match="cannot depend on itself"):
            Component(id="core", name="Core", files=["a.py"], dependencies=["core"])

    def test_duplicate_dependencies_removed(self):
        c = Component(id="core", name="Core", files=["a.py"], dependencies=["utils", "utils"])
        assert len(c.dependencies) == 1

    def test_get_file_extensions(self):
        c = Component(id="core", name="Core", files=["a.py", "b.ts", "c.py"])
        exts = c.get_file_extensions()
        assert "py" in exts
        assert "ts" in exts

    def test_with_layer(self):
        c = Component(id="core", name="Core", files=["a.py"], layer="domain")
        assert c.layer == "domain"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            Component(id="c", name="C", files=["a.py"], unknown_field="x")

    def test_model_dump_roundtrip(self):
        c = Component(id="svc", name="Service", files=["s.py"], tags=["api"])
        data = c.model_dump()
        restored = Component.model_validate(data)
        assert restored.id == "svc"
        assert restored.tags == ["api"]


# ---------------------------------------------------------------------------
# ArchitecturalMetric
# ---------------------------------------------------------------------------


class TestArchitecturalMetric:
    """Tests for ArchitecturalMetric model."""

    def test_create_basic(self):
        m = ArchitecturalMetric(
            component_id="core",
            metric_type="instability",
            value=0.5,
            description="Package instability",
        )
        assert m.component_id == "core"
        assert m.value == 0.5
        assert m.instability is None

    def test_martin_metrics(self):
        m = ArchitecturalMetric(
            component_id="svc",
            metric_type="distance",
            value=0.2,
            description="Distance from main sequence",
            instability=0.4,
            abstractness=0.6,
            distance=0.0,
        )
        assert m.instability == 0.4
        assert m.abstractness == 0.6
        assert m.distance == 0.0

    def test_instability_bounds(self):
        with pytest.raises(ValidationError):
            ArchitecturalMetric(
                component_id="c",
                metric_type="i",
                value=1.0,
                description="d",
                instability=1.5,
            )

    def test_abstractness_bounds(self):
        with pytest.raises(ValidationError):
            ArchitecturalMetric(
                component_id="c",
                metric_type="a",
                value=1.0,
                description="d",
                abstractness=-0.1,
            )

    def test_distance_bounds(self):
        with pytest.raises(ValidationError):
            ArchitecturalMetric(
                component_id="c",
                metric_type="d",
                value=1.0,
                description="d",
                distance=1.1,
            )


# ---------------------------------------------------------------------------
# DetectedPattern
# ---------------------------------------------------------------------------


class TestDetectedPattern:
    """Tests for DetectedPattern."""

    def test_create(self):
        p = DetectedPattern(
            pattern_type="singleton",
            confidence=0.85,
            components=["core"],
            description="Singleton pattern detected",
        )
        assert p.pattern_type == "singleton"
        assert p.confidence == 0.85

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            DetectedPattern(
                pattern_type="x",
                confidence=1.5,
                components=[],
                description="d",
            )

        with pytest.raises(ValidationError):
            DetectedPattern(
                pattern_type="x",
                confidence=-0.1,
                components=[],
                description="d",
            )


# ---------------------------------------------------------------------------
# QualityGateCheck / QualityGateResult
# ---------------------------------------------------------------------------


class TestQualityGateCheck:
    """Tests for QualityGateCheck."""

    def test_create_passed(self):
        c = QualityGateCheck(
            name="min_score",
            description="Minimum score check",
            passed=True,
            actual=85.0,
            threshold=70.0,
        )
        assert c.passed is True
        assert c.actual == 85.0
        assert c.threshold == 70.0

    def test_create_failed(self):
        c = QualityGateCheck(
            name="critical_issues",
            description="No critical issues",
            passed=False,
            actual=3.0,
            threshold=0.0,
        )
        assert c.passed is False


class TestQualityGateResult:
    """Tests for QualityGateResult."""

    def test_create_passing(self):
        r = QualityGateResult(
            passed=True,
            overall_score=90.0,
            grade="A",
        )
        assert r.passed is True
        assert r.overall_score == 90.0
        assert r.grade == "A"
        assert r.gate_checks == []
        assert r.recommendations == []

    def test_with_checks(self):
        check = QualityGateCheck(
            name="test", description="Test check", passed=True, actual=1.0, threshold=0.5
        )
        r = QualityGateResult(
            passed=True,
            overall_score=85.0,
            grade="B",
            gate_checks=[check],
            recommendations=["Add more tests"],
        )
        assert len(r.gate_checks) == 1
        assert len(r.recommendations) == 1

    def test_score_bounds(self):
        with pytest.raises(ValidationError):
            QualityGateResult(passed=True, overall_score=101.0, grade="A")

        with pytest.raises(ValidationError):
            QualityGateResult(passed=True, overall_score=-1.0, grade="F")

    def test_model_dump(self):
        r = QualityGateResult(passed=False, overall_score=45.0, grade="D")
        data = r.model_dump()
        assert data["passed"] is False
        assert data["overall_score"] == 45.0


# ---------------------------------------------------------------------------
# ModelMigrationTools
# ---------------------------------------------------------------------------


class TestModelMigrationTools:
    """Tests for ModelMigrationTools."""

    def test_init(self):
        tools = ModelMigrationTools(RepoConfig)
        assert tools.model_cls is RepoConfig

    def test_register_and_migrate(self):
        tools = ModelMigrationTools(RepoConfig)

        def migrate_1_to_2(data):
            data["schema_version"] = "2.0"
            return data

        tools.register_version_migration("1.0", "2.0", migrate_1_to_2)
        result = tools.migrate({"schema_version": "1.0"}, "1.0", "2.0")
        assert result["schema_version"] == "2.0"

    def test_migrate_same_version_returns_data(self):
        tools = ModelMigrationTools(RepoConfig)
        data = {"schema_version": "2.0"}
        result = tools.migrate(data, "2.0", "2.0")
        assert result == data

    def test_migrate_no_path_raises(self):
        tools = ModelMigrationTools(RepoConfig)
        with pytest.raises(ValueError, match="No migration path"):
            tools.migrate({}, "1.0", "3.0")

    def test_get_creation_timestamp(self):
        tools = ModelMigrationTools(RepoConfig)
        ts = tools.get_creation_timestamp()
        assert isinstance(ts, str)
        assert "T" in ts


# ---------------------------------------------------------------------------
# Layer / LayerViolation / ComponentExtractionStats
# ---------------------------------------------------------------------------


class TestLayer:
    def test_create(self):
        layer = Layer(name="domain", components=["core"], component_count=1)
        assert layer.name == "domain"
        assert layer.dependencies == []


class TestLayerViolation:
    def test_create(self):
        lv = LayerViolation(component_id="ui", expected_layer="presentation", actual_layer="domain")
        assert lv.component_id == "ui"


class TestComponentExtractionStats:
    def test_create(self):
        s = ComponentExtractionStats(components_found=5, edges_scanned=20)
        assert s.components_found == 5


# ---------------------------------------------------------------------------
# RepoConfig
# ---------------------------------------------------------------------------


class TestRepoConfig:
    """Tests for RepoConfig."""

    def test_defaults(self):
        rc = RepoConfig()
        assert rc.schema_version == "2.0"
        assert rc.extract_docstrings is True
        assert rc.min_pattern_confidence == 0.7
        assert "folder" in rc.detect_by

    def test_custom(self):
        rc = RepoConfig(
            schema_version="3.0",
            layers={"domain": ["src/domain/**"]},
            min_pattern_confidence=0.5,
        )
        assert rc.schema_version == "3.0"
        assert rc.layers is not None


# ---------------------------------------------------------------------------
# Vulnerability / DependencyRiskSummary / DependencyRiskReport
# ---------------------------------------------------------------------------


class TestVulnerability:
    def test_create(self):
        v = Vulnerability(
            id="CVE-2024-001",
            severity="high",
            summary="RCE in library",
            details="Remote code execution",
            affected_versions=["<1.0"],
            fixed_versions=["1.0.1"],
            references=["https://example.com"],
            published_date="2024-01-01",
            modified_date="2024-01-02",
        )
        assert v.id == "CVE-2024-001"


class TestDependencyRiskSummary:
    def test_create(self):
        s = DependencyRiskSummary(
            total_packages=10,
            vulnerable_packages=2,
            total_vulnerabilities=3,
            critical_vulnerabilities=1,
            high_vulnerabilities=1,
            moderate_vulnerabilities=1,
            low_vulnerabilities=0,
        )
        assert s.total_packages == 10


# ---------------------------------------------------------------------------
# HotspotPrediction / HotspotAnalysisResult
# ---------------------------------------------------------------------------


class TestHotspotPrediction:
    def test_create(self):
        hp = HotspotPrediction(component_id="core", score=0.8, confidence=0.9)
        assert hp.score == 0.8

    def test_score_bounds(self):
        with pytest.raises(ValidationError):
            HotspotPrediction(component_id="c", score=1.5, confidence=0.5)


# ---------------------------------------------------------------------------
# Graph models
# ---------------------------------------------------------------------------


class TestGraphNode:
    def test_create(self):
        n = GraphNode(id="n1", name="core", type="component")
        assert n.id == "n1"
        assert n.layer is None


class TestGraphEdge:
    def test_create(self):
        e = GraphEdge(source="n1", target="n2", type="dependency")
        assert e.weight == 1


class TestRuntimeData:
    def test_create(self):
        rd = RuntimeData(call_count=100, avg_duration_ms=5.5, error_rate=0.01)
        assert rd.call_count == 100


class TestArchitectureGraphMetrics:
    def test_create(self):
        m = ArchitectureGraphMetrics(
            total_components=5, total_dependencies=10, avg_complexity=3.2, hotspot_count=2
        )
        assert m.total_components == 5


class TestArchitectureGraphResponse:
    def test_create(self):
        r = ArchitectureGraphResponse(
            nodes=[GraphNode(id="n1", name="a", type="component")],
            edges=[],
            layers=["domain"],
            metrics=ArchitectureGraphMetrics(
                total_components=1, total_dependencies=0, avg_complexity=1.0, hotspot_count=0
            ),
        )
        assert len(r.nodes) == 1


# ---------------------------------------------------------------------------
# ArchitectureJobRequest
# ---------------------------------------------------------------------------


class TestArchitectureJobRequest:
    def test_create(self):
        req = ArchitectureJobRequest(
            codebase_id="my-project",
            repo_path=Path("/repo"),
        )
        assert req.codebase_id == "my-project"
        assert req.force_rebuild is False

    def test_invalid_codebase_id(self):
        with pytest.raises(ValidationError):
            ArchitectureJobRequest(
                codebase_id="my project!",
                repo_path=Path("/repo"),
            )


# ---------------------------------------------------------------------------
# QualityReport
# ---------------------------------------------------------------------------


class TestQualityReport:
    def test_create(self):
        qr = QualityReport(
            job_id="j1",
            codebase_id="proj",
            generated_at="2024-01-01T00:00:00",
            overall_score=8.5,
            grade="A",
            issues=[],
            summary={},
            recommendations=["Improve docs"],
            execution_time=1.5,
        )
        assert qr.overall_score == 8.5
        assert qr.grade == "A"


# ---------------------------------------------------------------------------
# ArchitectureRuntimeEdge / CodeGraphData
# ---------------------------------------------------------------------------


class TestArchitectureRuntimeEdge:
    def test_create(self):
        e = ArchitectureRuntimeEdge(
            source="a",
            target="b",
            call_count=10,
            avg_duration_ms=2.0,
            error_rate=0.05,
            confidence=0.95,
        )
        assert e.source == "a"


class TestCodeGraphData:
    def test_create(self):
        d = CodeGraphData(
            nodes=[{"id": "n1", "type": "function"}],
            edges=[{"source": "n1", "target": "n2"}],
        )
        assert len(d.nodes) == 1
