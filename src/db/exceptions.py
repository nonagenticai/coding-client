"""Database-specific exceptions for code graph operations.

This module provides custom exceptions for database operations to enable
more specific error handling and better error messages.
"""


class DatabaseError(Exception):
    """Base exception for all database-related errors."""

    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection cannot be established or is lost."""

    pass


class DatabaseIntegrityError(DatabaseError):
    """Raised when database integrity constraints are violated."""

    pass


class DatabaseOperationalError(DatabaseError):
    """Raised when database operations fail due to operational issues."""

    pass


class DatabaseSchemaError(DatabaseError):
    """Raised when database schema operations fail."""

    pass


class DatabaseMigrationError(DatabaseError):
    """Raised when database migrations fail."""

    pass


class DatabaseTransactionError(DatabaseError):
    """Raised when database transaction operations fail."""

    pass


class DatabaseQueryError(DatabaseError):
    """Raised when database queries fail or return unexpected results."""

    pass


class DatabaseLockError(DatabaseError):
    """Raised when database is locked and operations timeout."""

    pass
