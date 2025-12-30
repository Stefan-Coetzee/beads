"""
Pytest configuration and fixtures for the Learning Task Tracker tests.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from ltt.models.base import Base

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_test"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session_factory = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as session:
        yield session
        await session.rollback()
