"""Database abstraction layer for common database operations.

This module provides reusable database utilities and patterns to reduce
code duplication across services and repositories.
"""

from __future__ import annotations

import inspect
import logging
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from typing import (
    Any,
    TypeVar,
    cast,
)

from pydantic import BaseModel
from sqlalchemy import and_, func, select, update
from sqlalchemy.exc import DataError, IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Query, Session
from sqlalchemy.sql import Select

logger = logging.getLogger(__name__)

# Type variables for generic operations
T = TypeVar("T")
ModelType = TypeVar("ModelType")
SchemaType = TypeVar("SchemaType", bound=BaseModel)


class DatabaseError(Exception):
    """Base exception for database operations."""

    pass


class RecordNotFoundError(DatabaseError):
    """Raised when a requested record is not found."""

    pass


class DuplicateRecordError(DatabaseError):
    """Raised when trying to create a duplicate record."""

    pass


class DatabaseOperationError(DatabaseError):
    """Raised when a database operation fails."""

    pass


class BaseDatabaseOperations:
    """Base class for common database operations."""

    def __init__(self, model: type[ModelType]):
        """Initialize with a SQLAlchemy model.

        Args:
            model: SQLAlchemy model class
        """
        self.model = model

    @staticmethod
    def handle_database_error(func):
        """Decorator to handle common database errors."""

        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except IntegrityError as e:
                logger.error(f"Database integrity error: {e}")
                if "UNIQUE constraint" in str(e) or "duplicate key" in str(e).lower():
                    raise DuplicateRecordError("Record already exists") from e
                raise DatabaseOperationError(f"Database integrity error: {e}") from e
            except DataError as e:
                logger.error(f"Database data error: {e}")
                raise DatabaseOperationError(f"Invalid data: {e}") from e
            except OperationalError as e:
                logger.error(f"Database operational error: {e}")
                raise DatabaseOperationError(f"Database operation failed: {e}") from e
            except Exception as e:
                logger.error(f"Unexpected database error: {e}")
                raise DatabaseError(f"Unexpected error: {e}") from e

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except IntegrityError as e:
                logger.error(f"Database integrity error: {e}")
                if "UNIQUE constraint" in str(e) or "duplicate key" in str(e).lower():
                    raise DuplicateRecordError("Record already exists") from e
                raise DatabaseOperationError(f"Database integrity error: {e}") from e
            except DataError as e:
                logger.error(f"Database data error: {e}")
                raise DatabaseOperationError(f"Invalid data: {e}") from e
            except OperationalError as e:
                logger.error(f"Database operational error: {e}")
                raise DatabaseOperationError(f"Database operation failed: {e}") from e
            except Exception as e:
                logger.error(f"Unexpected database error: {e}")
                raise DatabaseError(f"Unexpected error: {e}") from e

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return wrapper


class SyncDatabaseOperations[ModelType](BaseDatabaseOperations):
    """Synchronous database operations."""

    def __init__(self, model: type[ModelType], session: Session):
        """Initialize with model and session.

        Args:
            model: SQLAlchemy model class
            session: SQLAlchemy session
        """
        super().__init__(model)
        self.session = session

    @BaseDatabaseOperations.handle_database_error
    def get_by_id(self, id: Any) -> ModelType | None:
        """Get a record by ID.

        Args:
            id: Record ID

        Returns:
            Model instance or None if not found
        """
        return cast(
            ModelType | None,
            self.session.query(self.model).filter(getattr(self.model, "id") == id).first(),
        )

    def get_by_id_or_404(self, id: Any) -> ModelType:
        """Get a record by ID or raise RecordNotFoundError.

        Args:
            id: Record ID

        Returns:
            Model instance

        Raises:
            RecordNotFoundError: If record not found
        """
        record = self.get_by_id(id)
        if not record:
            raise RecordNotFoundError(f"{self.model.__name__} with id {id} not found")
        return record

    @BaseDatabaseOperations.handle_database_error
    def get_all(
        self,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ModelType]:
        """Get all records with optional filtering and pagination.

        Args:
            filters: Dictionary of field:value filters
            order_by: Field name to order by (prefix with - for DESC)
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of model instances
        """
        query = self.session.query(self.model)

        # Apply filters
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    if isinstance(value, list):
                        query = query.filter(getattr(self.model, field).in_(value))
                    else:
                        query = query.filter(getattr(self.model, field) == value)

        # Apply ordering
        if order_by:
            if order_by.startswith("-"):
                field = order_by[1:]
                if hasattr(self.model, field):
                    query = query.order_by(getattr(self.model, field).desc())
            else:
                if hasattr(self.model, order_by):
                    query = query.order_by(getattr(self.model, order_by))

        # Apply pagination
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        return cast(list[ModelType], query.all())

    @BaseDatabaseOperations.handle_database_error
    def get_one(self, **kwargs: Any) -> ModelType | None:
        """Get a single record by field values.

        Args:
            **kwargs: Field:value pairs to filter by

        Returns:
            Model instance or None if not found
        """
        return cast(
            ModelType | None,
            self.session.query(self.model).filter_by(**kwargs).first(),
        )

    def get_one_or_404(self, **kwargs: Any) -> ModelType:
        """Get a single record by field values or raise RecordNotFoundError.

        Args:
            **kwargs: Field:value pairs to filter by

        Returns:
            Model instance

        Raises:
            RecordNotFoundError: If record not found
        """
        record = self.get_one(**kwargs)
        if not record:
            raise RecordNotFoundError(f"{self.model.__name__} not found with filters: {kwargs}")
        return record

    @BaseDatabaseOperations.handle_database_error
    def create(self, data: dict[str, Any] | BaseModel, commit: bool = True) -> ModelType:
        """Create a new record.

        Args:
            data: Dictionary or Pydantic schema with record data
            commit: Whether to commit the transaction

        Returns:
            Created model instance
        """
        data_dict: dict[str, Any]
        if isinstance(data, BaseModel):
            data_dict = data.model_dump(exclude_unset=True)
        else:
            data_dict = data

        instance = cast(ModelType, self.model(**data_dict))
        self.session.add(instance)

        if commit:
            self.session.commit()
            self.session.refresh(instance)

        return instance

    @BaseDatabaseOperations.handle_database_error
    def bulk_create(
        self, data_list: list[dict[str, Any] | BaseModel], commit: bool = True
    ) -> list[ModelType]:
        """Create multiple records.

        Args:
            data_list: List of dictionaries or Pydantic schemas
            commit: Whether to commit the transaction

        Returns:
            List of created model instances
        """
        instances: list[ModelType] = []
        for data in data_list:
            data_dict: dict[str, Any]
            if isinstance(data, BaseModel):
                data_dict = data.model_dump(exclude_unset=True)
            else:
                data_dict = data
            instance = cast(ModelType, self.model(**data_dict))
            instances.append(instance)
            self.session.add(instance)

        if commit:
            self.session.commit()
            for instance in instances:
                self.session.refresh(instance)

        return instances

    @BaseDatabaseOperations.handle_database_error
    def update(
        self, id: Any, data: dict[str, Any] | BaseModel, commit: bool = True
    ) -> ModelType | None:
        """Update a record by ID.

        Args:
            id: Record ID
            data: Dictionary or Pydantic schema with update data
            commit: Whether to commit the transaction

        Returns:
            Updated model instance or None if not found
        """
        instance = self.get_by_id(id)
        if not instance:
            return None

        data_dict: dict[str, Any]
        if isinstance(data, BaseModel):
            data_dict = data.model_dump(exclude_unset=True)
        else:
            data_dict = data

        for key, value in data_dict.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        if commit:
            self.session.commit()
            self.session.refresh(instance)

        return instance

    @BaseDatabaseOperations.handle_database_error
    def update_or_create(
        self, defaults: dict[str, Any], commit: bool = True, **kwargs: Any
    ) -> tuple[ModelType, bool]:
        """Update existing record or create new one.

        Args:
            defaults: Dictionary of default values for creation/update
            commit: Whether to commit the transaction
            **kwargs: Fields to search by

        Returns:
            Tuple of (instance, created) where created is True if a new record was created
        """
        existing = self.get_one(**kwargs)
        created = False

        if existing:
            # Update existing
            for key, value in defaults.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            instance = existing
        else:
            # Create new
            data = {**kwargs, **defaults}
            instance = cast(ModelType, self.model(**data))
            self.session.add(instance)
            created = True

        if commit:
            self.session.commit()
            self.session.refresh(instance)

        return instance, created

    @BaseDatabaseOperations.handle_database_error
    def delete(self, id: Any, commit: bool = True) -> bool:
        """Delete a record by ID.

        Args:
            id: Record ID
            commit: Whether to commit the transaction

        Returns:
            True if deleted, False if not found
        """
        instance = self.get_by_id(id)
        if not instance:
            return False

        self.session.delete(instance)

        if commit:
            self.session.commit()

        return True

    @BaseDatabaseOperations.handle_database_error
    def delete_many(self, filters: dict[str, Any], commit: bool = True) -> int:
        """Delete multiple records matching filters.

        Args:
            filters: Dictionary of field:value filters
            commit: Whether to commit the transaction

        Returns:
            Number of deleted records
        """
        query = self.session.query(self.model)

        for field, value in filters.items():
            if hasattr(self.model, field):
                if isinstance(value, list):
                    query = query.filter(getattr(self.model, field).in_(value))
                else:
                    query = query.filter(getattr(self.model, field) == value)

        count = query.count()
        query.delete()

        if commit:
            self.session.commit()

        return count

    @BaseDatabaseOperations.handle_database_error
    def count(self, filters: dict[str, Any] | None = None) -> int:
        """Count records with optional filtering.

        Args:
            filters: Dictionary of field:value filters

        Returns:
            Count of matching records
        """
        query = self.session.query(func.count(getattr(self.model, "id")))

        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    if isinstance(value, list):
                        query = query.filter(getattr(self.model, field).in_(value))
                    else:
                        query = query.filter(getattr(self.model, field) == value)

        result = query.scalar()
        return result if result is not None else 0

    @BaseDatabaseOperations.handle_database_error
    def exists(self, **kwargs: Any) -> bool:
        """Check if a record exists.

        Args:
            **kwargs: Field:value pairs to filter by

        Returns:
            True if exists, False otherwise
        """
        return self.session.query(
            self.session.query(self.model).filter_by(**kwargs).exists()
        ).scalar()

    def transaction(self):
        """Context manager for database transactions."""
        return database_transaction(self.session)


class AsyncDatabaseOperations[ModelType](BaseDatabaseOperations):
    """Asynchronous database operations."""

    def __init__(self, model: type[ModelType], session: AsyncSession):
        """Initialize with model and async session.

        Args:
            model: SQLAlchemy model class
            session: SQLAlchemy async session
        """
        super().__init__(model)
        self.session = session

    @BaseDatabaseOperations.handle_database_error
    async def get_by_id(self, id: Any) -> ModelType | None:
        """Get a record by ID.

        Args:
            id: Record ID

        Returns:
            Model instance or None if not found
        """
        result = await self.session.execute(
            select(self.model).where(getattr(self.model, "id") == id)
        )
        return cast(ModelType | None, result.scalar_one_or_none())

    @BaseDatabaseOperations.handle_database_error
    async def get_by_id_or_404(self, id: Any) -> ModelType:
        """Get a record by ID or raise RecordNotFoundError.

        Args:
            id: Record ID

        Returns:
            Model instance

        Raises:
            RecordNotFoundError: If record not found
        """
        record = await self.get_by_id(id)
        if not record:
            raise RecordNotFoundError(f"{self.model.__name__} with id {id} not found")
        return record

    @BaseDatabaseOperations.handle_database_error
    async def get_all(
        self,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ModelType]:
        """Get all records with optional filtering and pagination.

        Args:
            filters: Dictionary of field:value filters
            order_by: Field name to order by (prefix with - for DESC)
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of model instances
        """
        query = select(self.model)

        # Apply filters
        if filters:
            conditions = []
            for field, value in filters.items():
                if hasattr(self.model, field):
                    if isinstance(value, list):
                        conditions.append(getattr(self.model, field).in_(value))
                    else:
                        conditions.append(getattr(self.model, field) == value)
            if conditions:
                query = query.where(and_(*conditions))

        # Apply ordering
        if order_by:
            if order_by.startswith("-"):
                field = order_by[1:]
                if hasattr(self.model, field):
                    query = query.order_by(getattr(self.model, field).desc())
            else:
                if hasattr(self.model, order_by):
                    query = query.order_by(getattr(self.model, order_by))

        # Apply pagination
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return cast(list[ModelType], list(result.scalars().all()))

    @BaseDatabaseOperations.handle_database_error
    async def get_one(self, **kwargs: Any) -> ModelType | None:
        """Get a single record by field values.

        Args:
            **kwargs: Field:value pairs to filter by

        Returns:
            Model instance or None if not found
        """
        conditions = []
        for field, value in kwargs.items():
            if hasattr(self.model, field):
                conditions.append(getattr(self.model, field) == value)

        if not conditions:
            return None

        query = select(self.model).where(and_(*conditions))
        result = await self.session.execute(query)
        return cast(ModelType | None, result.scalar_one_or_none())

    async def get_one_or_404(self, **kwargs: Any) -> ModelType:
        """Get a single record by field values or raise RecordNotFoundError.

        Args:
            **kwargs: Field:value pairs to filter by

        Returns:
            Model instance

        Raises:
            RecordNotFoundError: If record not found
        """
        record = await self.get_one(**kwargs)
        if not record:
            raise RecordNotFoundError(f"{self.model.__name__} not found with filters: {kwargs}")
        return record

    @BaseDatabaseOperations.handle_database_error
    async def create(self, data: dict[str, Any] | BaseModel, commit: bool = True) -> ModelType:
        """Create a new record.

        Args:
            data: Dictionary or Pydantic schema with record data
            commit: Whether to commit the transaction

        Returns:
            Created model instance
        """
        data_dict: dict[str, Any]
        if isinstance(data, BaseModel):
            data_dict = data.model_dump(exclude_unset=True)
        else:
            data_dict = data

        instance = cast(ModelType, self.model(**data_dict))
        self.session.add(instance)

        if commit:
            await self.session.commit()
            await self.session.refresh(instance)

        return instance

    @BaseDatabaseOperations.handle_database_error
    async def update(
        self, id: Any, data: dict[str, Any] | BaseModel, commit: bool = True
    ) -> ModelType | None:
        """Update a record by ID.

        Args:
            id: Record ID
            data: Dictionary or Pydantic schema with update data
            commit: Whether to commit the transaction

        Returns:
            Updated model instance or None if not found
        """
        instance = await self.get_by_id(id)
        if not instance:
            return None

        data_dict: dict[str, Any]
        if isinstance(data, BaseModel):
            data_dict = data.model_dump(exclude_unset=True)
        else:
            data_dict = data

        for key, value in data_dict.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        if commit:
            await self.session.commit()
            await self.session.refresh(instance)

        return instance

    @BaseDatabaseOperations.handle_database_error
    async def delete(self, id: Any, commit: bool = True) -> bool:
        """Delete a record by ID.

        Args:
            id: Record ID
            commit: Whether to commit the transaction

        Returns:
            True if deleted, False if not found
        """
        instance = await self.get_by_id(id)
        if not instance:
            return False

        await self.session.delete(instance)

        if commit:
            await self.session.commit()

        return True

    async def transaction(self):
        """Context manager for async database transactions."""
        return async_database_transaction(self.session)


# Transaction context managers


@contextmanager
def database_transaction(session: Session):
    """Context manager for database transactions.

    Usage:
        with database_transaction(session) as trans:
            # Perform operations
            trans.commit()  # Explicit commit
        # Auto-rollback if no commit
    """
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    else:
        # If no explicit commit was called, rollback
        if session.new or session.dirty or session.deleted:
            session.rollback()


@asynccontextmanager
async def async_database_transaction(session: AsyncSession):
    """Async context manager for database transactions.

    Usage:
        async with async_database_transaction(session) as trans:
            # Perform operations
            await trans.commit()  # Explicit commit
        # Auto-rollback if no commit
    """
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    else:
        # If no explicit commit was called, rollback
        if session.new or session.dirty or session.deleted:
            await session.rollback()


# Utility functions


def paginate_query(
    query: Query, page: int = 1, per_page: int = 20, max_per_page: int = 100
) -> dict[str, Any]:
    """Add pagination to a query and return paginated results.

    Args:
        query: SQLAlchemy query
        page: Page number (1-indexed)
        per_page: Items per page
        max_per_page: Maximum allowed items per page

    Returns:
        Dictionary with items, total, page, per_page, pages
    """
    per_page = min(per_page, max_per_page)
    page = max(1, page)

    total = query.count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,  # Ceiling division
    }


async def async_paginate_query(
    session: AsyncSession,
    query: Select[Any],
    model: type[Any],
    page: int = 1,
    per_page: int = 20,
    max_per_page: int = 100,
) -> dict[str, Any]:
    """Add pagination to an async query and return paginated results.

    Args:
        session: Async SQLAlchemy session
        query: SQLAlchemy select statement
        model: Model class for counting
        page: Page number (1-indexed)
        per_page: Items per page
        max_per_page: Maximum allowed items per page

    Returns:
        Dictionary with items, total, page, per_page, pages
    """
    per_page = min(per_page, max_per_page)
    page = max(1, page)

    # Get total count
    count_query = select(func.count()).select_from(model)
    # Apply same where conditions as main query
    whereclause = getattr(query, "whereclause", None)
    if whereclause is not None:
        count_query = count_query.where(whereclause)

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated items
    paginated_query = query.limit(per_page).offset((page - 1) * per_page)
    result = await session.execute(paginated_query)
    items = result.scalars().all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total > 0 else 0,
    }


def bulk_update_mappings(
    session: Session,
    model: type[Any],
    mappings: list[dict[str, Any]],
    commit: bool = True,
) -> None:
    """Bulk update records using mappings.

    Args:
        session: SQLAlchemy session
        model: Model class
        mappings: List of dictionaries with updates (must include id)
        commit: Whether to commit the transaction
    """
    if not mappings:
        return

    # Use core update for each mapping since bulk_update_mappings expects a Mapper
    for mapping in mappings:
        mapping_copy = dict(mapping)
        record_id = mapping_copy.pop("id", None)
        if record_id is None:
            continue
        stmt = update(model).where(getattr(model, "id") == record_id).values(**mapping_copy)
        session.execute(stmt)

    if commit:
        session.commit()


async def async_bulk_update_mappings(
    session: AsyncSession,
    model: type[Any],
    mappings: list[dict[str, Any]],
    commit: bool = True,
) -> None:
    """Async bulk update records using mappings.

    Args:
        session: Async SQLAlchemy session
        model: Model class
        mappings: List of dictionaries with updates (must include id)
        commit: Whether to commit the transaction
    """
    if not mappings:
        return

    # For async, we need to use core update statements
    for mapping in mappings:
        mapping_copy = dict(mapping)
        record_id = mapping_copy.pop("id", None)
        if record_id is None:
            continue

        stmt = update(model).where(getattr(model, "id") == record_id).values(**mapping_copy)
        await session.execute(stmt)

    if commit:
        await session.commit()


# Repository base classes


class BaseRepository[ModelType]:
    """Base repository class for common patterns."""

    db: SyncDatabaseOperations[ModelType] | AsyncDatabaseOperations[ModelType]

    def __init__(self, model: type[ModelType], session: Session | AsyncSession):
        """Initialize repository.

        Args:
            model: SQLAlchemy model class
            session: Database session
        """
        self.model = model
        self.session = session

        # Initialize appropriate operations class
        if isinstance(session, AsyncSession):
            self.db = AsyncDatabaseOperations[ModelType](model, session)
        else:
            self.db = SyncDatabaseOperations[ModelType](model, session)


class SyncRepository(BaseRepository[ModelType]):
    """Base class for synchronous repositories."""

    db: SyncDatabaseOperations[ModelType]

    def __init__(self, model: type[ModelType], session: Session):
        """Initialize sync repository."""
        self.model = model
        self.session = session
        self.db = SyncDatabaseOperations[ModelType](model, session)


class AsyncRepository(BaseRepository[ModelType]):
    """Base class for asynchronous repositories."""

    db: AsyncDatabaseOperations[ModelType]

    def __init__(self, model: type[ModelType], session: AsyncSession):
        """Initialize async repository."""
        self.model = model
        self.session = session
        self.db = AsyncDatabaseOperations[ModelType](model, session)
