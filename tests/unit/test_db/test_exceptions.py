"""Tests for coding_client.db.exceptions module.

Validates the exception hierarchy: each exception class can be instantiated,
has the correct inheritance chain, and stores messages properly.
"""

import pytest
from coding_client.db.exceptions import (
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


class TestDatabaseErrorBase:
    """Tests for the base DatabaseError class."""

    def test_instantiate_with_message(self):
        exc = DatabaseError("something broke")
        assert str(exc) == "something broke"

    def test_inherits_from_exception(self):
        assert issubclass(DatabaseError, Exception)

    def test_is_catchable_as_exception(self):
        with pytest.raises(Exception):
            raise DatabaseError("test")


class TestDatabaseConnectionError:
    """Tests for DatabaseConnectionError."""

    def test_instantiate_with_message(self):
        exc = DatabaseConnectionError("connection refused")
        assert str(exc) == "connection refused"

    def test_inherits_from_database_error(self):
        assert issubclass(DatabaseConnectionError, DatabaseError)

    def test_catchable_as_database_error(self):
        with pytest.raises(DatabaseError):
            raise DatabaseConnectionError("conn lost")


class TestDatabaseIntegrityError:
    """Tests for DatabaseIntegrityError."""

    def test_instantiate_with_message(self):
        exc = DatabaseIntegrityError("unique constraint violated")
        assert str(exc) == "unique constraint violated"

    def test_inherits_from_database_error(self):
        assert issubclass(DatabaseIntegrityError, DatabaseError)


class TestDatabaseOperationalError:
    """Tests for DatabaseOperationalError."""

    def test_instantiate_with_message(self):
        exc = DatabaseOperationalError("disk full")
        assert str(exc) == "disk full"

    def test_inherits_from_database_error(self):
        assert issubclass(DatabaseOperationalError, DatabaseError)


class TestDatabaseSchemaError:
    """Tests for DatabaseSchemaError."""

    def test_instantiate_with_message(self):
        exc = DatabaseSchemaError("table missing")
        assert str(exc) == "table missing"

    def test_inherits_from_database_error(self):
        assert issubclass(DatabaseSchemaError, DatabaseError)


class TestDatabaseMigrationError:
    """Tests for DatabaseMigrationError."""

    def test_instantiate_with_message(self):
        exc = DatabaseMigrationError("migration 3 failed")
        assert str(exc) == "migration 3 failed"

    def test_inherits_from_database_error(self):
        assert issubclass(DatabaseMigrationError, DatabaseError)


class TestDatabaseTransactionError:
    """Tests for DatabaseTransactionError."""

    def test_instantiate_with_message(self):
        exc = DatabaseTransactionError("commit failed")
        assert str(exc) == "commit failed"

    def test_inherits_from_database_error(self):
        assert issubclass(DatabaseTransactionError, DatabaseError)


class TestDatabaseQueryError:
    """Tests for DatabaseQueryError."""

    def test_instantiate_with_message(self):
        exc = DatabaseQueryError("syntax error in SQL")
        assert str(exc) == "syntax error in SQL"

    def test_inherits_from_database_error(self):
        assert issubclass(DatabaseQueryError, DatabaseError)


class TestDatabaseLockError:
    """Tests for DatabaseLockError."""

    def test_instantiate_with_message(self):
        exc = DatabaseLockError("database is locked")
        assert str(exc) == "database is locked"

    def test_inherits_from_database_error(self):
        assert issubclass(DatabaseLockError, DatabaseError)


class TestExceptionHierarchyCatchAll:
    """Verify all sub-exceptions are catchable via the base class."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            DatabaseConnectionError,
            DatabaseIntegrityError,
            DatabaseOperationalError,
            DatabaseSchemaError,
            DatabaseMigrationError,
            DatabaseTransactionError,
            DatabaseQueryError,
            DatabaseLockError,
        ],
    )
    def test_all_subclasses_caught_by_database_error(self, exc_class):
        with pytest.raises(DatabaseError):
            raise exc_class("test")
