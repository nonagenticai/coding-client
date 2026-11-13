"""Tests for coding_client.db.tenant_query_helper module.

Tests add_tenant_filter, build_tenant_query, TenantQueryBuilder, and
validate_tenant_access with various SQL patterns and tenant scenarios.
"""

import pytest
from coding_client.db.tenant_query_helper import (
    LEGACY_TENANT_ID,
    TenantQueryBuilder,
    _extract_tenant_id,
    add_tenant_filter,
    build_tenant_query,
    validate_tenant_access,
)

# ---------------------------------------------------------------------------
# _extract_tenant_id
# ---------------------------------------------------------------------------


class TestExtractTenantId:
    """Tests for the internal _extract_tenant_id helper."""

    def test_string_passthrough(self):
        assert _extract_tenant_id("tenant-123") == "tenant-123"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            _extract_tenant_id("")

    def test_object_with_tenant_id_attribute(self):
        class Ctx:
            tenant_id = "from-attr"

        assert _extract_tenant_id(Ctx()) == "from-attr"

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Cannot extract tenant_id"):
            _extract_tenant_id(12345)


# ---------------------------------------------------------------------------
# add_tenant_filter
# ---------------------------------------------------------------------------


class TestAddTenantFilter:
    """Tests for add_tenant_filter function."""

    def test_no_where_clause(self):
        query, params = add_tenant_filter("SELECT * FROM nodes", "tenant-1")
        assert "WHERE tenant_id = ?" in query
        assert params == ["tenant-1"]

    def test_existing_where_clause(self):
        query, params = add_tenant_filter("SELECT * FROM nodes WHERE type = ?", "tenant-1")
        assert "tenant_id = ? AND" in query
        assert params == ["tenant-1"]

    def test_with_order_by(self):
        query, params = add_tenant_filter("SELECT * FROM nodes ORDER BY created_at", "tenant-1")
        assert "WHERE tenant_id = ?" in query
        assert "ORDER BY created_at" in query
        # tenant filter should appear before ORDER BY
        where_pos = query.upper().index("WHERE")
        order_pos = query.upper().index("ORDER BY")
        assert where_pos < order_pos

    def test_with_limit(self):
        query, params = add_tenant_filter("SELECT * FROM nodes LIMIT 10", "tenant-1")
        assert "WHERE tenant_id = ?" in query
        assert "LIMIT 10" in query

    def test_with_group_by(self):
        query, params = add_tenant_filter(
            "SELECT type, COUNT(*) FROM nodes GROUP BY type", "tenant-1"
        )
        assert "WHERE tenant_id = ?" in query
        assert "GROUP BY type" in query

    def test_with_table_alias(self):
        query, params = add_tenant_filter("SELECT * FROM nodes n", "tenant-1", table_alias="n")
        assert "n.tenant_id = ?" in query

    def test_custom_placeholder(self):
        query, params = add_tenant_filter("SELECT * FROM nodes", "tenant-1", param_placeholder="%s")
        assert "tenant_id = %s" in query

    def test_existing_where_with_order_by(self):
        query, params = add_tenant_filter("SELECT * FROM nodes WHERE type = ? ORDER BY id", "t-1")
        assert "tenant_id = ? AND" in query
        assert "ORDER BY id" in query
        assert params == ["t-1"]


# ---------------------------------------------------------------------------
# build_tenant_query
# ---------------------------------------------------------------------------


class TestBuildTenantQuery:
    """Tests for build_tenant_query function."""

    def test_no_existing_params(self):
        query, params = build_tenant_query("SELECT * FROM nodes", "tenant-1")
        assert "tenant_id = ?" in query
        assert params == ["tenant-1"]

    def test_with_existing_params(self):
        query, params = build_tenant_query(
            "SELECT * FROM nodes WHERE type = ?",
            "tenant-1",
            existing_params=["function"],
        )
        assert "tenant_id = ?" in query
        # Tenant param should come first
        assert params[0] == "tenant-1"
        assert "function" in params

    def test_with_table_alias(self):
        query, params = build_tenant_query("SELECT * FROM nodes n", "tenant-1", table_alias="n")
        assert "n.tenant_id = ?" in query

    def test_none_existing_params_defaults_to_empty(self):
        query, params = build_tenant_query("SELECT * FROM nodes", "tenant-1", existing_params=None)
        assert params == ["tenant-1"]


# ---------------------------------------------------------------------------
# TenantQueryBuilder
# ---------------------------------------------------------------------------


class TestTenantQueryBuilderBasic:
    """Tests for TenantQueryBuilder core query building."""

    def test_simple_select(self):
        builder = TenantQueryBuilder("nodes", "t-1")
        query, params = builder.build()
        assert query.startswith("SELECT * FROM nodes")
        assert "WHERE tenant_id = ?" in query
        assert params == ["t-1"]

    def test_select_specific_columns(self):
        builder = TenantQueryBuilder("nodes", "t-1")
        query, params = builder.select("id", "type").build()
        assert "SELECT id, type FROM nodes" in query
        assert params == ["t-1"]

    def test_where_condition(self):
        builder = TenantQueryBuilder("nodes", "t-1")
        query, params = builder.where("type = ?", "function").build()
        assert "tenant_id = ?" in query
        assert "AND type = ?" in query
        assert params == ["t-1", "function"]

    def test_multiple_where_conditions(self):
        builder = TenantQueryBuilder("nodes", "t-1")
        query, params = (
            builder.where("type = ?", "function").where("language = ?", "python").build()
        )
        assert params == ["t-1", "function", "python"]
        assert "AND type = ?" in query
        assert "AND language = ?" in query

    def test_order_by(self):
        builder = TenantQueryBuilder("nodes", "t-1")
        query, params = builder.order_by("created_at DESC").build()
        assert "ORDER BY created_at DESC" in query

    def test_limit_and_offset(self):
        builder = TenantQueryBuilder("nodes", "t-1")
        query, params = builder.limit(50).offset(10).build()
        assert "LIMIT 50" in query
        assert "OFFSET 10" in query

    def test_group_by(self):
        builder = TenantQueryBuilder("nodes", "t-1")
        query, params = builder.select("type", "COUNT(*)").group_by("type").build()
        assert "GROUP BY type" in query

    def test_join(self):
        builder = TenantQueryBuilder("nodes", "t-1")
        query, params = builder.join("JOIN edges ON nodes.id = edges.source").build()
        assert "JOIN edges ON nodes.id = edges.source" in query

    def test_table_alias(self):
        builder = TenantQueryBuilder("nodes", "t-1", table_alias="n")
        query, params = builder.build()
        assert "FROM nodes n" in query
        assert "n.tenant_id = ?" in query

    def test_fluent_chaining(self):
        """All builder methods return self for chaining."""
        builder = TenantQueryBuilder("nodes", "t-1")
        result = (
            builder.select("id")
            .join("JOIN edges e ON nodes.id = e.source")
            .where("type = ?", "func")
            .group_by("type")
            .order_by("id")
            .limit(10)
            .offset(0)
        )
        assert result is builder


class TestTenantQueryBuilderCount:
    """Tests for build_count method."""

    def test_count_query(self):
        builder = TenantQueryBuilder("nodes", "t-1")
        query, params = builder.build_count()
        assert "SELECT COUNT(*) FROM nodes" in query
        assert "WHERE tenant_id = ?" in query
        assert params == ["t-1"]

    def test_count_with_where(self):
        builder = TenantQueryBuilder("nodes", "t-1")
        query, params = builder.where("type = ?", "class").build_count()
        assert "tenant_id = ?" in query
        assert "AND type = ?" in query
        assert params == ["t-1", "class"]

    def test_count_with_group_by(self):
        builder = TenantQueryBuilder("nodes", "t-1")
        query, params = builder.group_by("type").build_count()
        assert "GROUP BY type" in query

    def test_count_with_alias(self):
        builder = TenantQueryBuilder("nodes", "t-1", table_alias="n")
        query, params = builder.build_count()
        assert "n.tenant_id = ?" in query


class TestTenantQueryBuilderDelete:
    """Tests for build_delete method."""

    def test_delete_query(self):
        builder = TenantQueryBuilder("nodes", "t-1")
        query, params = builder.build_delete()
        assert query.startswith("DELETE FROM nodes")
        assert "WHERE tenant_id = ?" in query
        assert params == ["t-1"]

    def test_delete_with_where(self):
        builder = TenantQueryBuilder("nodes", "t-1")
        query, params = builder.where("type = ?", "orphan").build_delete()
        assert "tenant_id = ?" in query
        assert "AND type = ?" in query
        assert params == ["t-1", "orphan"]


class TestTenantQueryBuilderEmptyTenant:
    """Test that empty tenant_id raises during construction."""

    def test_empty_tenant_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            TenantQueryBuilder("nodes", "")


# ---------------------------------------------------------------------------
# validate_tenant_access
# ---------------------------------------------------------------------------


class TestValidateTenantAccess:
    """Tests for validate_tenant_access function."""

    def test_matching_tenant(self):
        assert validate_tenant_access("tenant-1", "tenant-1") is True

    def test_mismatched_tenant(self):
        assert validate_tenant_access("tenant-1", "tenant-2") is False

    def test_none_resource_tenant_allows_legacy_by_default(self):
        assert validate_tenant_access(None, "tenant-1") is True

    def test_none_resource_tenant_denies_when_legacy_disabled(self):
        assert validate_tenant_access(None, "tenant-1", allow_legacy=False) is False

    def test_legacy_tenant_id_allows_by_default(self):
        assert validate_tenant_access(LEGACY_TENANT_ID, "tenant-1") is True

    def test_legacy_tenant_id_denies_when_legacy_disabled(self):
        assert validate_tenant_access(LEGACY_TENANT_ID, "tenant-1", allow_legacy=False) is False

    def test_empty_user_tenant_denies(self):
        assert validate_tenant_access("tenant-1", "") is False

    def test_object_with_tenant_id_attribute(self):
        class UserCtx:
            tenant_id = "tenant-1"

        assert validate_tenant_access("tenant-1", UserCtx()) is True

    def test_object_with_can_access_method(self):
        class UserCtx:
            tenant_id = "tenant-1"

            def can_access(self, resource_tenant_id):
                return resource_tenant_id == "special"

        assert validate_tenant_access("special", UserCtx()) is True
        assert validate_tenant_access("other", UserCtx()) is False
