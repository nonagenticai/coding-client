"""Database layer for coding-client.

Provides:
- PostgreSQL connection management (via PgBouncer)
- Tenant-aware query building
- Generic database type aliases
- Custom database exceptions
"""

from . import db_types, exceptions, postgres_connection, tenant_query_helper
from .exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseIntegrityError,
    DatabaseLockError,
    DatabaseMigrationError,
    DatabaseOperationalError,
    DatabaseQueryError,
    DatabaseSchemaError,
    DatabaseTransactionError,
)
from .tenant_query_helper import TenantQueryBuilder

__all__ = [
    # Submodules
    "db_types",
    "exceptions",
    "postgres_connection",
    "tenant_query_helper",
    # Key classes
    "TenantQueryBuilder",
    # Exceptions
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseIntegrityError",
    "DatabaseLockError",
    "DatabaseMigrationError",
    "DatabaseOperationalError",
    "DatabaseQueryError",
    "DatabaseSchemaError",
    "DatabaseTransactionError",
]
