"""
Database connection and session management for the Learning Task Tracker.

Uses SQLAlchemy 2.0 async engine with asyncpg driver.
"""

import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev",
)


# Global engine and session factory
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Get or create the global async database engine.

    Returns:
        AsyncEngine instance configured for PostgreSQL with asyncpg
    """
    global _engine

    if _engine is None:
        _engine = create_async_engine(
            DATABASE_URL,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
            pool_pre_ping=True,  # Verify connections before using
            pool_size=5,
            max_overflow=10,
        )

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Get or create the global async session factory.

    Returns:
        Async session factory for creating database sessions
    """
    global _session_factory

    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Allow accessing attributes after commit
        )

    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database sessions in FastAPI or other async contexts.

    Yields:
        AsyncSession instance

    Usage:
        async with get_session() as session:
            # Use session here
            pass

        # Or with FastAPI dependency injection:
        @app.get("/items")
        async def read_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_engine() -> None:
    """
    Close the database engine and release all connections.

    Call this during application shutdown.
    """
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
