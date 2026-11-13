"""
Tenant Query Helper for Database Operations.

This module provides utilities for adding tenant isolation to database queries.
It ensures that all queries properly filter by tenant_id to prevent BOLA vulnerabilities.

Usage:
    from db.tenant_query_helper import (
        add_tenant_filter,
        build_tenant_query,
        TenantQueryBuilder,
    )

    # Simple case - add tenant filter to existing query
    query = add_tenant_filter("SELECT * FROM nodes", "tenant-123")
    # Result: "SELECT * FROM nodes WHERE tenant_id = ?"

    # Complex case - with existing WHERE clause
    query = add_tenant_filter(
        "SELECT * FROM nodes WHERE type = ?",
        "tenant-123"
    )
    # Result: "SELECT * FROM nodes WHERE tenant_id = ? AND type = ?"

    # Using the builder for more control
    builder = TenantQueryBuilder("nodes", "tenant-123")
    query, params = builder.select().where("type = ?", "function").build()
"""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class _HasTenantId(Protocol):
    """Protocol for objects that provide at minimum a tenant_id attribute."""

    @property
    def tenant_id(self) -> str: ...


logger = logging.getLogger(__name__)


def _extract_tenant_id(tenant: str) -> str:
    """Extract tenant_id string from a string value.

    Args:
        tenant: A tenant_id string.

    Returns:
        The tenant_id string.

    Raises:
        ValueError: If tenant_id is empty or None.
    """
    if isinstance(tenant, str):
        if not tenant:
            raise ValueError("tenant_id cannot be empty")
        return tenant

    # For TenantContext-like objects, try to get tenant_id attribute
    if hasattr(tenant, "tenant_id"):
        return tenant.tenant_id

    raise ValueError(f"Cannot extract tenant_id from {type(tenant)}")


# Default tenant ID for legacy data (matches migration 003)
LEGACY_TENANT_ID = "legacy"


def add_tenant_filter(
    query: str,
    tenant: str,
    table_alias: str = "",
    param_placeholder: str = "?",
) -> tuple[str, list[Any]]:
    """
    Add tenant_id filter to an existing SQL query.

    This function handles different query structures:
    - Queries without WHERE clause: adds WHERE tenant_id = ?
    - Queries with WHERE clause: adds AND tenant_id = ? after WHERE
    - Queries with ORDER BY/LIMIT: inserts filter before those clauses

    Args:
        query: The SQL query to modify
        tenant: The tenant ID string
        table_alias: Optional table alias prefix (e.g., "n" for "n.tenant_id")
        param_placeholder: Placeholder for parameters (default "?" for SQLite)

    Returns:
        Tuple of (modified_query, [tenant_id]) for use with parameterized queries

    Example:
        >>> query, params = add_tenant_filter("SELECT * FROM nodes", "tenant-123")
        >>> cursor.execute(query, params)
    """
    tenant_id = _extract_tenant_id(tenant)
    if not tenant_id:
        logger.warning("add_tenant_filter called with empty tenant_id")
        return query, []

    # Build the tenant column reference
    tenant_col = f"{table_alias}.tenant_id" if table_alias else "tenant_id"

    # Normalize query for analysis
    query_upper = query.upper()

    # Find the position of WHERE if it exists
    where_pos = -1
    where_match = re.search(r"\bWHERE\b", query_upper)
    if where_match:
        where_pos = where_match.start()

    # Find positions of ORDER BY, GROUP BY, LIMIT, etc.
    end_markers = ["ORDER BY", "GROUP BY", "LIMIT", "OFFSET", "HAVING"]
    end_pos = len(query)
    for marker in end_markers:
        marker_match = re.search(rf"\b{marker}\b", query_upper)
        if marker_match and marker_match.start() < end_pos:
            # Only consider markers after WHERE
            if where_pos == -1 or marker_match.start() > where_pos:
                end_pos = marker_match.start()

    # Build the tenant filter
    tenant_filter = f"{tenant_col} = {param_placeholder}"

    if where_pos == -1:
        # No WHERE clause - insert WHERE before end markers
        modified_query = query[:end_pos].rstrip() + f" WHERE {tenant_filter} " + query[end_pos:]
    else:
        # WHERE clause exists - insert AND after WHERE
        # Find the end of "WHERE " to insert after it
        assert where_match is not None  # guaranteed by where_pos != -1
        where_end = where_match.end()
        # Insert the tenant filter right after WHERE, with AND connecting to existing conditions
        modified_query = query[:where_end] + f" {tenant_filter} AND " + query[where_end:].lstrip()

    return modified_query.strip(), [tenant_id]


def build_tenant_query(
    base_query: str,
    tenant: str,
    existing_params: list[Any] | None = None,
    table_alias: str = "",
) -> tuple[str, list[Any]]:
    """
    Build a complete query with tenant filtering and combine parameters.

    Args:
        base_query: The SQL query to modify
        tenant: The tenant ID string
        existing_params: Existing query parameters
        table_alias: Optional table alias prefix

    Returns:
        Tuple of (modified_query, combined_params)

    Example:
        >>> query, params = build_tenant_query(
        ...     "SELECT * FROM nodes WHERE type = ?",
        ...     "tenant-123",
        ...     existing_params=["function"]
        ... )
        >>> # query = "SELECT * FROM nodes WHERE tenant_id = ? AND type = ?"
        >>> # params = ["tenant-123", "function"]
    """
    if existing_params is None:
        existing_params = []

    modified_query, tenant_params = add_tenant_filter(base_query, tenant, table_alias)

    # Tenant ID should be the first parameter for WHERE tenant_id = ? AND ...
    combined_params = tenant_params + list(existing_params)

    return modified_query, combined_params


class TenantQueryBuilder:
    """
    Fluent query builder with automatic tenant isolation.

    This builder ensures all queries include proper tenant filtering
    and helps construct complex queries with correct parameter ordering.

    Example:
        builder = TenantQueryBuilder("nodes", "tenant-123")
        query, params = (
            builder
            .select("id", "type", "properties")
            .where("type = ?", "function")
            .where("json_extract(properties, '$.name') LIKE ?", "%handler%")
            .order_by("created_at DESC")
            .limit(50)
            .offset(0)
            .build()
        )
    """

    def __init__(
        self,
        table_name: str,
        tenant: str,
        table_alias: str = "",
    ):
        """
        Initialize the query builder.

        Args:
            table_name: Name of the primary table
            tenant: Tenant ID string for isolation
            table_alias: Optional alias for the table
        """
        self.table_name = table_name
        self.tenant_id = _extract_tenant_id(tenant)
        self.table_alias = table_alias

        self._columns: list[str] = ["*"]
        self._joins: list[str] = []
        self._where_conditions: list[str] = []
        self._where_params: list[Any] = []
        self._group_by: str | None = None
        self._order_by: str | None = None
        self._limit: int | None = None
        self._offset: int | None = None

    def select(self, *columns: str) -> TenantQueryBuilder:
        """Specify columns to select."""
        if columns:
            self._columns = list(columns)
        return self

    def join(self, join_clause: str) -> TenantQueryBuilder:
        """Add a JOIN clause."""
        self._joins.append(join_clause)
        return self

    def where(self, condition: str, *params: Any) -> TenantQueryBuilder:
        """Add a WHERE condition with parameters."""
        self._where_conditions.append(condition)
        self._where_params.extend(params)
        return self

    def group_by(self, *columns: str) -> TenantQueryBuilder:
        """Add GROUP BY clause."""
        self._group_by = ", ".join(columns)
        return self

    def order_by(self, *columns: str) -> TenantQueryBuilder:
        """Add ORDER BY clause."""
        self._order_by = ", ".join(columns)
        return self

    def limit(self, limit: int) -> TenantQueryBuilder:
        """Add LIMIT clause."""
        self._limit = limit
        return self

    def offset(self, offset: int) -> TenantQueryBuilder:
        """Add OFFSET clause."""
        self._offset = offset
        return self

    def build(self) -> tuple[str, list[Any]]:
        """
        Build the complete query with tenant isolation.

        Returns:
            Tuple of (query_string, parameters_list)
        """
        # Build SELECT clause
        columns_str = ", ".join(self._columns)
        table_ref = f"{self.table_name} {self.table_alias}" if self.table_alias else self.table_name
        query = f"SELECT {columns_str} FROM {table_ref}"

        # Add JOINs
        if self._joins:
            query += " " + " ".join(self._joins)

        # Build WHERE clause with tenant isolation first
        tenant_col = f"{self.table_alias}.tenant_id" if self.table_alias else "tenant_id"

        where_parts = [f"{tenant_col} = ?"]
        params: list[Any] = [self.tenant_id]

        for condition in self._where_conditions:
            where_parts.append(condition)
        params.extend(self._where_params)

        query += " WHERE " + " AND ".join(where_parts)

        # Add GROUP BY
        if self._group_by:
            query += f" GROUP BY {self._group_by}"

        # Add ORDER BY
        if self._order_by:
            query += f" ORDER BY {self._order_by}"

        # Add LIMIT
        if self._limit is not None:
            query += f" LIMIT {self._limit}"

        # Add OFFSET
        if self._offset is not None:
            query += f" OFFSET {self._offset}"

        return query, params

    def build_count(self) -> tuple[str, list[Any]]:
        """
        Build a COUNT(*) query with tenant isolation.

        Returns:
            Tuple of (query_string, parameters_list)
        """
        table_ref = f"{self.table_name} {self.table_alias}" if self.table_alias else self.table_name
        query = f"SELECT COUNT(*) FROM {table_ref}"

        # Add JOINs
        if self._joins:
            query += " " + " ".join(self._joins)

        # Build WHERE clause with tenant isolation
        tenant_col = f"{self.table_alias}.tenant_id" if self.table_alias else "tenant_id"

        where_parts = [f"{tenant_col} = ?"]
        params: list[Any] = [self.tenant_id]

        for condition in self._where_conditions:
            where_parts.append(condition)
        params.extend(self._where_params)

        query += " WHERE " + " AND ".join(where_parts)

        # Add GROUP BY for count queries if needed
        if self._group_by:
            query += f" GROUP BY {self._group_by}"

        return query, params

    def build_delete(self) -> tuple[str, list[Any]]:
        """
        Build a DELETE query with tenant isolation.

        Returns:
            Tuple of (query_string, parameters_list)
        """
        query = f"DELETE FROM {self.table_name}"

        # Build WHERE clause with tenant isolation
        where_parts = ["tenant_id = ?"]
        params: list[Any] = [self.tenant_id]

        for condition in self._where_conditions:
            where_parts.append(condition)
        params.extend(self._where_params)

        query += " WHERE " + " AND ".join(where_parts)

        return query, params


def validate_tenant_access(
    resource_tenant_id: str | None,
    user_tenant: str | _HasTenantId,
    allow_legacy: bool | None = None,
) -> bool:
    """
    Validate that a user has access to a resource based on tenant IDs.

    Args:
        resource_tenant_id: The tenant_id of the resource
        user_tenant: The user's tenant_id string or an object with a tenant_id attribute
        allow_legacy: Whether to allow access to legacy (NULL) tenant data.
                      Defaults to True if not specified.

    Returns:
        True if access is allowed, False otherwise
    """
    user_tenant_id: str
    # Handle objects with tenant_id attribute (e.g. TenantContext)
    if isinstance(user_tenant, _HasTenantId):
        if allow_legacy is None:
            allow_legacy_attr: Any = getattr(user_tenant, "allow_legacy_access", None)
            if allow_legacy_attr is not None:
                allow_legacy = bool(allow_legacy_attr)
        can_access_method: Any = getattr(user_tenant, "can_access", None)
        if callable(can_access_method):
            result: bool = can_access_method(resource_tenant_id)
            return result
        user_tenant_id = user_tenant.tenant_id
    else:
        user_tenant_id = user_tenant

    if allow_legacy is None:
        allow_legacy = True

    if not user_tenant_id:
        return False

    if resource_tenant_id is None:
        # NULL tenant_id - allow if legacy access is permitted
        return allow_legacy

    if resource_tenant_id == LEGACY_TENANT_ID:
        # Legacy tenant data - allow if legacy access is permitted
        return allow_legacy

    # Normal case - must match exactly
    return resource_tenant_id == user_tenant_id
