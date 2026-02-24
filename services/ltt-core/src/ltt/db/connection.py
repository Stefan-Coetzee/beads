"""
Database connection and session management for the Learning Task Tracker.

Uses SQLAlchemy 2.0 async engine with asyncpg driver.

FOR SCRIPTS/TESTS (this module):
- Uses NullPool by default (no connection reuse)
- Safe for any async context
- Slight performance cost but rock-solid reliability

FOR PRODUCTION (use api.database instead):
- FastAPI manages database lifecycle
- Uses QueuePool with proper connection pooling
- Pool initialized in the event loop for correct binding
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, QueuePool

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev",
)

# NullPool = no connection reuse = no async issues
# Set DB_USE_NULL_POOL=false only if you know what you're doing
USE_NULL_POOL = os.getenv("DB_USE_NULL_POOL", "true").lower() == "true"


def _create_engine() -> AsyncEngine:
    """Create the async engine with appropriate pooling."""
    engine_kwargs = {
        "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
    }

    if USE_NULL_POOL:
        # NullPool: Fresh connection per operation
        # - No event loop binding issues
        # - No "another operation in progress" errors
        # - Slightly slower (connection overhead per query)
        engine_kwargs["poolclass"] = NullPool
    else:
        # QueuePool: Connection reuse
        # - Faster (reuses connections)
        # - REQUIRES: Engine created in same event loop where used
        # - REQUIRES: Proper session scoping to avoid concurrent ops
        engine_kwargs["poolclass"] = QueuePool
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_size"] = 10
        engine_kwargs["max_overflow"] = 20

    return create_async_engine(DATABASE_URL, **engine_kwargs)


# =============================================================================
# Simple Global Access
# =============================================================================

# Engine created at import time - with NullPool this is safe
_engine: AsyncEngine = _create_engine()
_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def get_engine() -> AsyncEngine:
    """Get the database engine."""
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the session factory for creating sessions."""
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session.

    Usage:
        async with get_session() as session:
            result = await session.execute(...)
    """
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_engine() -> None:
    """Close the database engine. Call at application shutdown."""
    global _engine
    await _engine.dispose()


# =============================================================================
# For Testing / Reconfiguration
# =============================================================================


def reset_engine() -> None:
    """Reset engine (for testing). Creates fresh engine on next access."""
    global _engine, _session_factory
    _engine = _create_engine()
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
