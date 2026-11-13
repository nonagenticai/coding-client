"""
Database configuration and session management for code_graph_helper.

This module defines a global SQLAlchemy async engine for PostgreSQL.
The database URL is pulled from the DATABASE_URL environment variable.
"""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

# Grab the database URL from the environment.
#
# ⛔ NO DEFAULT. This used to fall back to
# ``postgres:postgres@localhost:5432/code_graph_helper`` -- a host Postgres that no
# longer exists (George ruling 2026-10-21: no service or test defaults to a host
# :5432). Importing this module without DATABASE_URL (or TEST_DATABASE_URL) now
# refuses with a message naming the variable, instead of building an engine that
# points at nothing. (As of 2026-10-21 no consumer of the coding-client package
# imports this module; coding-repo-jobs, the only one, uses its own engine.)
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("TEST_DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set -- coding_client.db_init has no default database. "
        "Set DATABASE_URL=postgresql+psycopg://<user>:<pw>@<host>:<port>/<db> "
        "(or TEST_DATABASE_URL in tests)."
    )

# Convert postgresql:// to postgresql+psycopg:// for async psycopg3 driver
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Create the async engine
engine = create_async_engine(DATABASE_URL, future=True, echo=False)

# Factory for creating new async sessions
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Base class for declarative models
Base = declarative_base()


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Yield a database session for dependency injection."""
    async with AsyncSessionLocal() as session:
        yield session
