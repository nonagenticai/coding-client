"""Tests for coding_client.models.core module."""

from __future__ import annotations

import pytest
from coding_client.models.core import (
    AnalysisResponse,
    CodebaseAnalysisRequest,
    CodeSecurityPattern,
    CoreAnalysisResult,
    CoreCodeEntity,
    CoreComplexityMetrics,
    CoreFileAnalysisResult,
    DependencyInfoModel,
    EntityRelation,
    EntityType,
    FullAnalysis,
    GraphMetrics,
    IncrementalAnalysis,
    OverallGraphMetrics,
    RelationType,
    RepositoryAnalysis,
    SnippetEvaluation,
    SourceLocation,
    TypeInfo,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# EntityType enum
# ---------------------------------------------------------------------------


class TestEntityType:
    """Tests for EntityType enum."""

    def test_has_function(self):
        assert EntityType.FUNCTION == "function"

    def test_has_class(self):
        assert EntityType.CLASS == "class"

    def test_has_module(self):
        assert EntityType.MODULE == "module"

    def test_has_file(self):
        assert EntityType.FILE == "file"

    def test_has_variable(self):
        assert EntityType.VARIABLE == "variable"

    def test_has_interface(self):
        assert EntityType.INTERFACE == "interface"

    def test_has_import(self):
        assert EntityType.IMPORT == "import"

    def test_has_struct(self):
        assert EntityType.STRUCT == "struct"

    def test_has_enum(self):
        assert EntityType.ENUM == "enum"

    def test_has_trait(self):
        assert EntityType.TRAIT == "trait"

    def test_has_namespace(self):
        assert EntityType.NAMESPACE == "namespace"

    def test_has_lambda(self):
        assert EntityType.LAMBDA == "lambda"

    def test_all_members_are_strings(self):
        for member in EntityType:
            assert isinstance(member.value, str)

    def test_lookup_from_string(self):
        assert EntityType("function") is EntityType.FUNCTION


# ---------------------------------------------------------------------------
# RelationType enum
# ---------------------------------------------------------------------------


class TestRelationType:
    """Tests for RelationType enum."""

    def test_has_calls(self):
        assert RelationType.CALLS == "calls"

    def test_has_imports(self):
        assert RelationType.IMPORTS == "imports"

    def test_has_inherits(self):
        assert RelationType.INHERITS == "inherits"

    def test_has_contains(self):
        assert RelationType.CONTAINS == "contains"

    def test_has_depends_on(self):
        assert RelationType.DEPENDS_ON == "depends_on"

    def test_has_implements(self):
        assert RelationType.IMPLEMENTS == "implements"

    def test_has_references(self):
        assert RelationType.REFERENCES == "references"

    def test_legacy_aliases_resolve_correctly(self):
        assert RelationType.INHERITANCE == RelationType.INHERITS
        assert RelationType.CALL == RelationType.CALLS
        assert RelationType.IMPORT == RelationType.IMPORTS
        assert RelationType.DEPENDENCY == RelationType.DEPENDS_ON
        assert RelationType.USAGE == RelationType.REFERENCES
        assert RelationType.COMPOSITION == RelationType.CONTAINS


# ---------------------------------------------------------------------------
# SourceLocation
# ---------------------------------------------------------------------------


class TestSourceLocation:
    """Tests for SourceLocation model."""

    def test_create_valid(self):
        loc = SourceLocation(
            file_path="src/main.py",
            line_start=1,
            line_end=10,
            column_start=0,
            column_end=40,
        )
        assert loc.file_path == "src/main.py"
        assert loc.line_start == 1
        assert loc.line_end == 10

    def test_is_frozen(self):
        loc = SourceLocation(
            file_path="a.py", line_start=1, line_end=1, column_start=0, column_end=5
        )
        with pytest.raises(ValidationError):
            loc.file_path = "b.py"

    def test_line_start_ge_1(self):
        with pytest.raises(ValidationError):
            SourceLocation(file_path="a.py", line_start=0, line_end=1, column_start=0, column_end=5)


# ---------------------------------------------------------------------------
# TypeInfo
# ---------------------------------------------------------------------------


class TestTypeInfo:
    """Tests for TypeInfo model."""

    def test_create_minimal(self):
        t = TypeInfo(name="int")
        assert t.name == "int"
        assert t.module is None
        assert t.is_generic is False
        assert t.generic_params == []

    def test_create_full(self):
        t = TypeInfo(
            name="List",
            module="typing",
            is_generic=True,
            generic_params=["int"],
            is_nullable=True,
            is_array=True,
            array_dimensions=2,
        )
        assert t.is_generic is True
        assert t.generic_params == ["int"]
        assert t.is_nullable is True
        assert t.array_dimensions == 2


# ---------------------------------------------------------------------------
# CoreCodeEntity
# ---------------------------------------------------------------------------


class TestCoreCodeEntity:
    """Tests for CoreCodeEntity model."""

    def _make_entity(self, **overrides):
        defaults = {
            "id": "e1",
            "name": "my_func",
            "type": EntityType.FUNCTION,
            "language": "python",
            "file_path": "src/app.py",
            "line_number": 10,
        }
        defaults.update(overrides)
        return CoreCodeEntity(**defaults)

    def test_create_with_required_fields(self):
        entity = self._make_entity()
        assert entity.id == "e1"
        assert entity.name == "my_func"
        assert entity.type == EntityType.FUNCTION
        assert entity.language == "python"
        assert entity.file_path == "src/app.py"
        assert entity.line_number == 10

    def test_optional_fields_default_none_or_false(self):
        entity = self._make_entity()
        assert entity.end_line_number is None
        assert entity.column_start is None
        assert entity.visibility is None
        assert entity.is_static is False
        assert entity.is_abstract is False
        assert entity.is_final is False
        assert entity.is_async is False
        assert entity.is_generic is False
        assert entity.code_snippet is None
        assert entity.docstring is None
        assert entity.signature is None
        assert entity.source_code is None
        assert entity.return_type is None
        assert entity.parameter_types == []
        assert entity.properties == {}
        assert entity.metadata == {}

    def test_with_return_type(self):
        ti = TypeInfo(name="str")
        entity = self._make_entity(return_type=ti)
        assert entity.return_type is not None
        assert entity.return_type.name == "str"

    def test_model_dump_roundtrip(self):
        entity = self._make_entity(visibility="public", is_static=True)
        data = entity.model_dump()
        assert data["visibility"] == "public"
        assert data["is_static"] is True
        restored = CoreCodeEntity.model_validate(data)
        assert restored.id == entity.id
        assert restored.is_static is True

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            CoreCodeEntity(
                id="e1",
                name="x",
                type=EntityType.FUNCTION,
                language="python",
                # missing file_path and line_number
            )


# ---------------------------------------------------------------------------
# EntityRelation
# ---------------------------------------------------------------------------


class TestEntityRelation:
    """Tests for EntityRelation model."""

    def test_create_with_required_fields(self):
        rel = EntityRelation(
            source_id="a",
            target_id="b",
            type=RelationType.CALLS,
        )
        assert rel.source_id == "a"
        assert rel.target_id == "b"
        assert rel.type == RelationType.CALLS

    def test_weight_default(self):
        rel = EntityRelation(source_id="a", target_id="b", type=RelationType.CALLS)
        assert rel.weight == 1.0

    def test_weight_bounds(self):
        rel = EntityRelation(source_id="a", target_id="b", type=RelationType.CALLS, weight=0.5)
        assert rel.weight == 0.5

        with pytest.raises(ValidationError):
            EntityRelation(source_id="a", target_id="b", type=RelationType.CALLS, weight=1.5)

        with pytest.raises(ValidationError):
            EntityRelation(source_id="a", target_id="b", type=RelationType.CALLS, weight=-0.1)

    def test_auto_generated_id(self):
        rel = EntityRelation(source_id="a", target_id="b", type=RelationType.CALLS)
        assert rel.id == "a-calls-b"

    def test_backward_compat_relationship_type(self):
        rel = EntityRelation(source_id="a", target_id="b", relationship_type="imports")
        assert rel.type == RelationType.IMPORTS

    def test_model_dump_roundtrip(self):
        rel = EntityRelation(
            source_id="mod1",
            target_id="func1",
            type=RelationType.CONTAINS,
            weight=0.9,
            context="module scope",
        )
        data = rel.model_dump()
        assert data["source_id"] == "mod1"
        assert data["weight"] == 0.9
        restored = EntityRelation.model_validate(data)
        assert restored.type == RelationType.CONTAINS


# ---------------------------------------------------------------------------
# DependencyInfoModel
# ---------------------------------------------------------------------------


class TestDependencyInfoModel:
    """Tests for DependencyInfoModel."""

    def test_create_with_required(self):
        dep = DependencyInfoModel(module_name="requests", import_type="import")
        assert dep.module_name == "requests"
        assert dep.import_type == "import"
        assert dep.line_number == 0
        assert dep.is_external is False

    def test_optional_fields(self):
        dep = DependencyInfoModel(
            module_name="os.path",
            import_type="from_import",
            alias="osp",
            line_number=5,
            is_external=True,
        )
        assert dep.alias == "osp"
        assert dep.is_external is True


# ---------------------------------------------------------------------------
# CoreComplexityMetrics
# ---------------------------------------------------------------------------


class TestCoreComplexityMetrics:
    """Tests for CoreComplexityMetrics model."""

    def test_all_defaults(self):
        m = CoreComplexityMetrics()
        assert m.cyclomatic_complexity == 0.0
        assert m.cognitive_complexity == 0.0
        assert m.lines_of_code == 0
        assert m.logical_lines == 0
        assert m.parameters_count == 0
        assert m.returns_count == 0
        assert m.branches_count == 0
        assert m.nested_depth == 0
        assert m.maintainability_index == 0.0
        assert m.halstead_volume == 0.0
        assert m.halstead_difficulty == 0.0
        assert m.halstead_effort == 0.0
        assert m.function_count == 0
        assert m.class_count == 0
        assert m.comment_lines == 0
        assert m.blank_lines == 0
        assert m.docstring_coverage == 0.0

    def test_is_frozen(self):
        m = CoreComplexityMetrics(cyclomatic_complexity=5.0)
        with pytest.raises(ValidationError):
            m.cyclomatic_complexity = 10.0

    def test_custom_values(self):
        m = CoreComplexityMetrics(
            cyclomatic_complexity=12.0,
            cognitive_complexity=8.0,
            lines_of_code=100,
            nested_depth=4,
        )
        assert m.cyclomatic_complexity == 12.0
        assert m.lines_of_code == 100


# ---------------------------------------------------------------------------
# CodeSecurityPattern
# ---------------------------------------------------------------------------


class TestCodeSecurityPattern:
    """Tests for CodeSecurityPattern."""

    def test_create(self):
        p = CodeSecurityPattern(
            type="sql_injection",
            severity="high",
            line_number=42,
            description="Potential SQL injection",
        )
        assert p.type == "sql_injection"
        assert p.severity == "high"
        assert p.cwe_id is None

    def test_with_cwe(self):
        p = CodeSecurityPattern(
            type="xss",
            severity="critical",
            line_number=10,
            description="XSS detected",
            cwe_id="CWE-79",
        )
        assert p.cwe_id == "CWE-79"


# ---------------------------------------------------------------------------
# CoreAnalysisResult
# ---------------------------------------------------------------------------


class TestCoreAnalysisResult:
    """Tests for CoreAnalysisResult model."""

    def test_create_successful(self):
        r = CoreAnalysisResult(
            success=True,
            language="python",
            file_path="src/main.py",
        )
        assert r.success is True
        assert r.entities == []
        assert r.relationships == []
        assert r.dependencies == []
        assert r.error is None
        assert r.errors == []
        assert r.warnings == []

    def test_create_failed(self):
        r = CoreAnalysisResult(
            success=False,
            language="go",
            file_path="main.go",
            error="parse error",
        )
        assert r.success is False
        assert r.error == "parse error"

    def test_with_entities(self):
        entity = CoreCodeEntity(
            id="e1",
            name="main",
            type=EntityType.FUNCTION,
            language="python",
            file_path="main.py",
            line_number=1,
        )
        r = CoreAnalysisResult(
            success=True,
            language="python",
            file_path="main.py",
            entities=[entity],
        )
        assert len(r.entities) == 1
        assert r.entities[0].name == "main"

    def test_model_dump(self):
        r = CoreAnalysisResult(success=True, language="rust", file_path="lib.rs", total_lines=200)
        data = r.model_dump()
        assert data["total_lines"] == 200
        assert data["success"] is True


# ---------------------------------------------------------------------------
# CoreFileAnalysisResult
# ---------------------------------------------------------------------------


class TestCoreFileAnalysisResult:
    """Tests for CoreFileAnalysisResult."""

    def test_create(self):
        analysis = CoreAnalysisResult(success=True, language="python", file_path="a.py")
        far = CoreFileAnalysisResult(file_path="a.py", language="python", analysis_result=analysis)
        assert far.file_path == "a.py"
        assert far.timestamp is not None


# ---------------------------------------------------------------------------
# RepositoryAnalysis
# ---------------------------------------------------------------------------


class TestRepositoryAnalysis:
    """Tests for RepositoryAnalysis."""

    def test_create(self):
        ra = RepositoryAnalysis(success=True)
        assert ra.success is True
        assert ra.file_results == []
        assert ra.failed_files == []


# ---------------------------------------------------------------------------
# FullAnalysis / IncrementalAnalysis / SnippetEvaluation
# ---------------------------------------------------------------------------


class TestFullAnalysis:
    """Tests for FullAnalysis."""

    def test_create(self):
        fa = FullAnalysis(success=True)
        assert fa.success is True
        assert fa.file_results == []
        assert fa.patterns == []
        assert fa.architecture_analysis == {}
        assert fa.error is None


class TestIncrementalAnalysis:
    """Tests for IncrementalAnalysis."""

    def test_create(self):
        ia = IncrementalAnalysis(success=True)
        assert ia.success is True
        assert ia.changed_files == []
        assert ia.impact_analysis == {}


class TestSnippetEvaluation:
    """Tests for SnippetEvaluation."""

    def test_create(self):
        se = SnippetEvaluation(success=True)
        assert se.success is True
        assert se.compatibility_score == 0.0
        assert se.recommendations == []


# ---------------------------------------------------------------------------
# GraphMetrics / OverallGraphMetrics
# ---------------------------------------------------------------------------


class TestGraphMetrics:
    """Tests for GraphMetrics."""

    def test_create(self):
        gm = GraphMetrics(entity_id="e1", entity_name="main")
        assert gm.entity_id == "e1"
        assert gm.degree_centrality == 0.0
        assert gm.pagerank == 0.0


class TestOverallGraphMetrics:
    """Tests for OverallGraphMetrics."""

    def test_create(self):
        og = OverallGraphMetrics()
        assert og.node_count == 0
        assert og.edge_count == 0
        assert og.density == 0.0


# ---------------------------------------------------------------------------
# CodebaseAnalysisRequest
# ---------------------------------------------------------------------------


class TestCodebaseAnalysisRequest:
    """Tests for CodebaseAnalysisRequest."""

    def test_create_with_directory_only(self):
        req = CodebaseAnalysisRequest(directory="/src")
        assert req.directory == "/src"
        assert req.languages == ["python"]
        assert req.max_workers is None
        assert req.include_tests is False
        assert req.ignore_patterns == []

    def test_custom_languages(self):
        req = CodebaseAnalysisRequest(
            directory="/repo",
            languages=["python", "javascript"],
            include_tests=True,
            ignore_patterns=["*.pyc"],
        )
        assert "javascript" in req.languages
        assert req.include_tests is True
        assert req.ignore_patterns == ["*.pyc"]

    def test_model_dump_roundtrip(self):
        req = CodebaseAnalysisRequest(directory="/app", max_workers=4)
        data = req.model_dump()
        restored = CodebaseAnalysisRequest.model_validate(data)
        assert restored.directory == "/app"
        assert restored.max_workers == 4


# ---------------------------------------------------------------------------
# AnalysisResponse
# ---------------------------------------------------------------------------


class TestAnalysisResponse:
    """Tests for AnalysisResponse."""

    def test_create(self):
        resp = AnalysisResponse(
            status="success",
            directory="/repo",
            files_processed=10,
            files_failed=1,
            total_entities=50,
            total_relations=30,
            processing_time={},
            languages=["python"],
        )
        assert resp.status == "success"
        assert resp.files_processed == 10
        assert resp.total_entities == 50
