"""Tests for coding_client.db.db_types module.

Validates TypedDict types can be instantiated with correct fields and that
type hints are accessible via __annotations__.
"""

from datetime import UTC, datetime

from coding_client.db.db_types import (
    AnalysisSession,
    CoreLanguageStats,
    EdgeProperties,
    EdgeRecord,
    LanguageSummary,
    NodeProperties,
    NodeRecord,
    SchemaVersion,
)


class TestNodeProperties:
    """Tests for NodeProperties TypedDict."""

    def test_create_with_all_fields(self):
        props: NodeProperties = {
            "name": "my_func",
            "qualified_name": "module.my_func",
            "path": "/src/module.py",
            "file_path": "/src/module.py",
            "docstring": "A function.",
            "complexity": 5,
            "return_type": {"type": "int"},
            "parameter_types": [{"name": "x", "type": "str"}],
            "properties": {"key": "val"},
            "metadata": {"source": "ast"},
            "content_hash": "abc123",
        }
        assert props["name"] == "my_func"
        assert props["complexity"] == 5

    def test_create_partial(self):
        """NodeProperties has total=False, so partial dicts are valid."""
        props: NodeProperties = {"name": "partial_func"}
        assert props["name"] == "partial_func"

    def test_annotations_contain_expected_keys(self):
        expected = {"name", "qualified_name", "path", "file_path", "docstring", "complexity"}
        assert expected.issubset(set(NodeProperties.__annotations__))


class TestEdgeProperties:
    """Tests for EdgeProperties TypedDict."""

    def test_create_with_all_fields(self):
        props: EdgeProperties = {
            "weight": 1.5,
            "context": "call site",
            "location_file": "/src/a.py",
            "location_line": 42,
            "location_column": 8,
        }
        assert props["weight"] == 1.5
        assert props["location_line"] == 42

    def test_create_partial(self):
        props: EdgeProperties = {"weight": 0.8}
        assert props["weight"] == 0.8


class TestNodeRecord:
    """Tests for NodeRecord TypedDict."""

    def test_create_full_record(self):
        now = datetime.now(UTC)
        record: NodeRecord = {
            "id": "node-1",
            "type": "function",
            "properties": '{"name": "foo"}',
            "created_at": now,
            "updated_at": now,
            "content_hash": "sha256abc",
            "file_size": 1024,
            "language": "python",
            "file_path": "/src/foo.py",
            "line_number": 10,
            "column_start": 0,
            "column_end": 40,
            "visibility": "public",
            "is_static": False,
            "is_abstract": False,
            "is_final": False,
            "is_async": True,
            "signature": "async def foo(x: int) -> str",
            "docstring": "Does stuff.",
        }
        assert record["id"] == "node-1"
        assert record["is_async"] is True
        assert record["language"] == "python"

    def test_annotations_contain_multi_language_fields(self):
        annotations = NodeRecord.__annotations__
        for field in (
            "language",
            "file_path",
            "line_number",
            "visibility",
            "is_async",
            "signature",
        ):
            assert field in annotations, f"Missing field: {field}"


class TestEdgeRecord:
    """Tests for EdgeRecord TypedDict."""

    def test_create_full_record(self):
        now = datetime.now(UTC)
        record: EdgeRecord = {
            "id": 1,
            "source": "node-a",
            "target": "node-b",
            "relationship": "calls",
            "properties": '{"context": "direct"}',
            "weight": 1.0,
            "created_at": now,
            "context": "function call",
            "location_file": "/src/a.py",
            "location_line": 55,
            "location_column": 4,
        }
        assert record["source"] == "node-a"
        assert record["relationship"] == "calls"


class TestLanguageTypes:
    """Tests for CoreLanguageStats and LanguageSummary TypedDicts."""

    def test_core_language_stats(self):
        now = datetime.now(UTC)
        stats: CoreLanguageStats = {
            "language": "python",
            "file_path": "/src/main.py",
            "entity_count": 42,
            "relationship_count": 100,
            "lines_of_code": 500,
            "complexity_score": 3.7,
            "last_analyzed": now,
        }
        assert stats["language"] == "python"
        assert stats["entity_count"] == 42

    def test_language_summary(self):
        summary: LanguageSummary = {
            "file_count": 10,
            "total_entities": 200,
            "total_relationships": 500,
            "total_lines": 5000,
            "avg_complexity": 4.2,
        }
        assert summary["file_count"] == 10
        assert summary["avg_complexity"] == 4.2


class TestSchemaVersionAndAnalysisSession:
    """Tests for SchemaVersion and AnalysisSession TypedDicts."""

    def test_schema_version(self):
        now = datetime.now(UTC)
        sv: SchemaVersion = {
            "version": 6,
            "description": "Add language stats table",
            "applied_at": now,
        }
        assert sv["version"] == 6

    def test_analysis_session(self):
        now = datetime.now(UTC)
        session: AnalysisSession = {
            "id": "sess-001",
            "started_at": now,
            "completed_at": now,
            "languages": '["python", "javascript"]',
            "files_processed": 50,
            "files_failed": 2,
            "total_entities": 300,
            "total_relationships": 800,
            "status": "completed",
            "error_message": None,
        }
        assert session["status"] == "completed"
        assert session["files_failed"] == 2
