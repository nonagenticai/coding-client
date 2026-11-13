"""
PostgreSQL connection manager for code_graph_helper.

Designed to work with PgBouncer connection pooler.
Applications connect through PgBouncer, which handles connection pooling to PostgreSQL.

Architecture:
    Application -> PgBouncer (connection pooler) -> PostgreSQL

PgBouncer handles:
    - Connection pooling
    - Connection reuse
    - Load balancing

This module provides:
    - Simple connection creation (no pooling needed)
    - Transaction management
    - Query builders for graph operations
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
from psycopg import sql

# get_settings is provided by the service layer (e.g., from app.core.config)
# Services must call set_settings_provider() before using postgres_connection
_settings_provider = None


def set_settings_provider(provider):
    """Set the settings provider function. Call this from your service startup."""
    global _settings_provider
    _settings_provider = provider


def get_settings():
    """Get settings from the configured provider."""
    if _settings_provider is None:
        raise RuntimeError("Settings provider not configured. Call set_settings_provider() first.")
    return _settings_provider()


logger = logging.getLogger(__name__)

# Connection parameters (cached)
_connection_params: dict | None = None


def _get_connection_params() -> dict:
    """
    Get PostgreSQL connection parameters.

    Returns:
        Dictionary of connection parameters for psycopg
    """
    global _connection_params

    if _connection_params is None:
        settings = get_settings()
        db_settings = settings.database

        _connection_params = db_settings.as_connection_params()

        logger.info(
            "PostgreSQL connection configured via PgBouncer: %s:%s/%s",
            _connection_params["host"],
            _connection_params["port"],
            _connection_params["dbname"],
        )

    return _connection_params


async def init_postgres_pool():
    """
    Initialize PostgreSQL connection (for compatibility).

    Note: When using PgBouncer, we don't create a connection pool.
    PgBouncer handles pooling. This function just validates connectivity.

    Returns:
        None
    """
    logger.info("Validating PostgreSQL connection through PgBouncer...")

    try:
        async with get_postgres_connection() as conn:
            cur = await conn.execute("SELECT version()")
            row = await cur.fetchone()
            version = row[0] if row else "unknown"
            logger.info(f"PostgreSQL connection established (via PgBouncer): {version[:80]}...")

            # Verify we can access the schema
            cur = await conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
            )
            row = await cur.fetchone()
            table_count = row[0] if row else 0
            logger.info(f"Found {table_count} tables in database")

    except Exception as e:
        # SECURITY: Don't log exception details that might contain passwords
        logger.error("Failed to connect to PostgreSQL through PgBouncer: %s", type(e).__name__)
        raise


async def close_postgres_pool():
    """
    Close PostgreSQL connections (for compatibility).

    Note: When using PgBouncer, individual connections are closed automatically.
    This is a no-op for compatibility with pooled connection APIs.
    """
    logger.info("PostgreSQL connections will be closed by PgBouncer")
    # No-op when using PgBouncer


@asynccontextmanager
async def get_postgres_connection() -> AsyncIterator[psycopg.AsyncConnection]:
    """
    Context manager for creating a PostgreSQL connection through PgBouncer.

    Usage:
        async with get_postgres_connection() as conn:
            cur = await conn.execute("SELECT * FROM nodes LIMIT 10")
            rows = cur.fetchall()

    Note:
        - Connects through PgBouncer, which handles connection pooling
        - Each connection is lightweight and managed by PgBouncer
        - Connection is automatically closed when context exits

    Yields:
        psycopg AsyncConnection instance
    """
    import asyncio

    params = _get_connection_params()

    # Build conninfo string from params dict
    conninfo_parts = []
    param_map = {
        "host": "host",
        "port": "port",
        "user": "user",
        "password": "password",
        "dbname": "dbname",
    }
    for key, conninfo_key in param_map.items():
        if key in params and params[key]:
            conninfo_parts.append(f"{conninfo_key}={params[key]}")

    # Add server_settings as options
    server_settings = params.get("server_settings", {})
    if server_settings.get("application_name"):
        conninfo_parts.append(f"application_name={server_settings['application_name']}")

    conninfo = " ".join(conninfo_parts)

    conn = await asyncio.wait_for(
        psycopg.AsyncConnection.connect(conninfo=conninfo, autocommit=True),
        timeout=params.get("timeout", 30.0),
    )

    try:
        # Set session parameters
        settings = get_settings()
        db_settings = settings.database

        if db_settings.statement_timeout > 0:
            await conn.execute(
                sql.SQL("SET statement_timeout = {}").format(
                    sql.Literal(db_settings.statement_timeout)
                )
            )

        yield conn

    finally:
        await conn.close()


@asynccontextmanager
async def postgres_transaction() -> AsyncIterator[psycopg.AsyncConnection]:
    """
    Context manager for PostgreSQL transactions.

    Usage:
        async with postgres_transaction() as conn:
            await conn.execute("INSERT INTO nodes ...")
            await conn.execute("INSERT INTO edges ...")
            # Automatically commits on success, rolls back on exception

    Yields:
        psycopg AsyncConnection instance with active transaction
    """
    import asyncio

    params = _get_connection_params()

    # Build conninfo string from params dict
    conninfo_parts = []
    param_map = {
        "host": "host",
        "port": "port",
        "user": "user",
        "password": "password",
        "dbname": "dbname",
    }
    for key, conninfo_key in param_map.items():
        if key in params and params[key]:
            conninfo_parts.append(f"{conninfo_key}={params[key]}")

    server_settings = params.get("server_settings", {})
    if server_settings.get("application_name"):
        conninfo_parts.append(f"application_name={server_settings['application_name']}")

    conninfo = " ".join(conninfo_parts)

    # autocommit=False enables transaction mode
    conn = await asyncio.wait_for(
        psycopg.AsyncConnection.connect(conninfo=conninfo, autocommit=False),
        timeout=params.get("timeout", 30.0),
    )

    try:
        yield conn
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()


class PostgresQueryBuilder:
    """
    Helper class for building secure PostgreSQL graph queries with parameterized statements.

    SECURITY: All methods use parameterized queries to prevent SQL injection.

    TENANT ISOLATION: All queries that accept tenant_id will filter results to only
    include data belonging to that tenant. When tenant_id is None, no filtering is applied
    (for admin access or legacy compatibility).
    """

    @staticmethod
    def find_descendants(
        start_node_id: str,
        max_depth: int = 10,
        edge_types: list[str] | None = None,
        tenant_id: str | None = None,
    ) -> tuple[str, list]:
        """
        Build recursive CTE query to find all descendants of a node.

        SECURITY: Uses parameterized queries to prevent SQL injection.

        Args:
            start_node_id: Starting node ID
            max_depth: Maximum traversal depth
            edge_types: Optional list of edge types to filter by
            tenant_id: Optional tenant ID for data isolation

        Returns:
            Tuple of (SQL query string with placeholders, list of parameter values)

        Usage:
            query, params = PostgresQueryBuilder.find_descendants("node_123", tenant_id="tenant_abc")
            cur = await conn.execute(query, params)
            results = cur.fetchall()
        """
        params: list[str | int | list[str]] = [start_node_id, start_node_id, max_depth]
        edge_filter = ""
        tenant_filter = ""

        if edge_types:
            params.append(edge_types)
            edge_filter = "AND e.edge_type = ANY(%s)"

        if tenant_id:
            params.extend([tenant_id, tenant_id])
            tenant_filter = "AND n.tenant_id = %s AND e.tenant_id = %s"

        query = f"""
            WITH RECURSIVE descendants AS (
                -- Base case
                SELECT
                    e.target_id as node_id,
                    n.name,
                    n.node_type,
                    1 as depth,
                    ARRAY[%s, e.target_id] as path,
                    e.edge_type
                FROM edges e
                JOIN nodes n ON e.target_id = n.node_id
                WHERE e.source_id = %s
                {edge_filter}
                {tenant_filter}

                UNION ALL

                -- Recursive case
                SELECT
                    e.target_id,
                    n.name,
                    n.node_type,
                    d.depth + 1,
                    d.path || e.target_id,
                    e.edge_type
                FROM descendants d
                JOIN edges e ON d.node_id = e.source_id
                JOIN nodes n ON e.target_id = n.node_id
                WHERE e.target_id != ALL(d.path)
                  AND d.depth < %s
                {edge_filter}
                {tenant_filter}
            )
            SELECT DISTINCT
                node_id,
                name,
                node_type,
                depth,
                path,
                edge_type
            FROM descendants
            ORDER BY depth, name
        """

        return query, params

    @staticmethod
    def find_ancestors(
        start_node_id: str,
        max_depth: int = 10,
        edge_types: list[str] | None = None,
        tenant_id: str | None = None,
    ) -> tuple[str, list]:
        """
        Build recursive CTE query to find all ancestors of a node.

        SECURITY: Uses parameterized queries to prevent SQL injection.

        Args:
            start_node_id: Starting node ID
            max_depth: Maximum traversal depth
            edge_types: Optional list of edge types to filter by
            tenant_id: Optional tenant ID for data isolation

        Returns:
            Tuple of (SQL query string with placeholders, list of parameter values)

        Usage:
            query, params = PostgresQueryBuilder.find_ancestors("node_123", tenant_id="tenant_abc")
            cur = await conn.execute(query, params)
            results = cur.fetchall()
        """
        params: list[str | int | list[str]] = [start_node_id, start_node_id, max_depth]
        edge_filter = ""
        tenant_filter = ""

        if edge_types:
            params.append(edge_types)
            edge_filter = "AND e.edge_type = ANY(%s)"

        if tenant_id:
            params.extend([tenant_id, tenant_id])
            tenant_filter = "AND n.tenant_id = %s AND e.tenant_id = %s"

        query = f"""
            WITH RECURSIVE ancestors AS (
                -- Base case
                SELECT
                    e.source_id as node_id,
                    n.name,
                    n.node_type,
                    1 as depth,
                    ARRAY[e.source_id, %s] as path,
                    e.edge_type
                FROM edges e
                JOIN nodes n ON e.source_id = n.node_id
                WHERE e.target_id = %s
                {edge_filter}
                {tenant_filter}

                UNION ALL

                -- Recursive case
                SELECT
                    e.source_id,
                    n.name,
                    n.node_type,
                    a.depth + 1,
                    e.source_id || a.path,
                    e.edge_type
                FROM ancestors a
                JOIN edges e ON a.node_id = e.target_id
                JOIN nodes n ON e.source_id = n.node_id
                WHERE e.source_id != ALL(a.path)
                  AND a.depth < %s
                {edge_filter}
                {tenant_filter}
            )
            SELECT DISTINCT
                node_id,
                name,
                node_type,
                depth,
                path,
                edge_type
            FROM ancestors
            ORDER BY depth, name
        """

        return query, params

    @staticmethod
    def find_call_graph(
        function_name: str,
        direction: str = "outgoing",
        max_depth: int = 3,
        tenant_id: str | None = None,
    ) -> tuple[str, list]:
        """
        Build query to find function call graph.

        SECURITY: Uses parameterized queries to prevent SQL injection.

        Args:
            function_name: Function name to start from
            direction: 'outgoing' for callees, 'incoming' for callers
            max_depth: Maximum call depth
            tenant_id: Optional tenant ID for data isolation

        Returns:
            Tuple of (SQL query string with placeholders, list of parameter values)

        Usage:
            query, params = PostgresQueryBuilder.find_call_graph("my_function", tenant_id="tenant_abc")
            cur = await conn.execute(query, params)
            results = cur.fetchall()
        """
        params = [function_name, function_name, max_depth]
        tenant_filter = ""

        if tenant_id:
            params.append(tenant_id)
            tenant_filter = "AND n.tenant_id = %s"

        if direction == "outgoing":
            query = f"""
                WITH RECURSIVE call_graph AS (
                    -- Base case: direct calls
                    SELECT
                        ce.callee_id as function_id,
                        n.name as function_name,
                        n.file_path,
                        1 as depth,
                        ARRAY[(SELECT node_id FROM nodes WHERE name = %s {tenant_filter} LIMIT 1), ce.callee_id] as path
                    FROM call_edges ce
                    JOIN nodes n ON ce.callee_id = n.node_id
                    WHERE ce.caller_id = (SELECT node_id FROM nodes WHERE name = %s {tenant_filter} LIMIT 1)
                    {tenant_filter}

                    UNION ALL

                    -- Recursive case
                    SELECT
                        ce.callee_id,
                        n.name,
                        n.file_path,
                        cg.depth + 1,
                        cg.path || ce.callee_id
                    FROM call_graph cg
                    JOIN call_edges ce ON cg.function_id = ce.caller_id
                    JOIN nodes n ON ce.callee_id = n.node_id
                    WHERE ce.callee_id != ALL(cg.path)
                      AND cg.depth < %s
                    {tenant_filter}
                )
                SELECT DISTINCT * FROM call_graph ORDER BY depth, function_name
            """
        else:  # incoming
            query = f"""
                WITH RECURSIVE call_graph AS (
                    -- Base case: direct callers
                    SELECT
                        ce.caller_id as function_id,
                        n.name as function_name,
                        n.file_path,
                        1 as depth,
                        ARRAY[ce.caller_id, (SELECT node_id FROM nodes WHERE name = %s {tenant_filter} LIMIT 1)] as path
                    FROM call_edges ce
                    JOIN nodes n ON ce.caller_id = n.node_id
                    WHERE ce.callee_id = (SELECT node_id FROM nodes WHERE name = %s {tenant_filter} LIMIT 1)
                    {tenant_filter}

                    UNION ALL

                    -- Recursive case
                    SELECT
                        ce.caller_id,
                        n.name,
                        n.file_path,
                        cg.depth + 1,
                        ce.caller_id || cg.path
                    FROM call_graph cg
                    JOIN call_edges ce ON cg.function_id = ce.callee_id
                    JOIN nodes n ON ce.caller_id = n.node_id
                    WHERE ce.caller_id != ALL(cg.path)
                      AND cg.depth < %s
                    {tenant_filter}
                )
                SELECT DISTINCT * FROM call_graph ORDER BY depth, function_name
            """

        return query, params

    @staticmethod
    def find_circular_dependencies() -> str:
        """
        Build query to find circular import dependencies.

        Returns:
            SQL query string
        """
        return """
            WITH RECURSIVE dependency_chain AS (
                SELECT
                    ie.importer_id as start_node,
                    ie.importer_id,
                    ie.imported_module,
                    ARRAY[ie.importer_id] as path,
                    1 as depth
                FROM import_edges ie

                UNION ALL

                SELECT
                    dc.start_node,
                    ie.importer_id,
                    ie.imported_module,
                    dc.path || ie.importer_id,
                    dc.depth + 1
                FROM dependency_chain dc
                JOIN import_edges ie ON dc.imported_module = ie.importer_id
                WHERE ie.importer_id != ALL(dc.path)
                  AND dc.depth < 50
            )
            SELECT
                start_node,
                path || ARRAY[imported_module] as cycle_path,
                depth as cycle_length
            FROM dependency_chain
            WHERE imported_module = start_node
            ORDER BY cycle_length, start_node
        """


# Export public API
__all__ = [
    "init_postgres_pool",
    "close_postgres_pool",
    "get_postgres_connection",
    "postgres_transaction",
    "PostgresQueryBuilder",
]
