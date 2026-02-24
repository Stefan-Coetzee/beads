"""
Shared test fixtures for the api-server LTI integration tests.

Fixtures:
  - test_settings:        Settings(auth_enabled=False, debug=True)
  - test_settings_auth:   Settings(auth_enabled=True, debug=True)
  - async_engine:         SQLAlchemy engine → ltt_test database
  - async_session:        Per-test DB session (rolled back)
  - session_factory:      async_sessionmaker for get_session_factory() callers
  - fake_redis_client:    fakeredis.FakeRedis instance
  - lti_storage:          RedisLaunchDataStorage backed by fake Redis
  - app:                  FastAPI app with patched DB + Redis + settings
  - client:               httpx.AsyncClient for the test app
  - app_auth / client_auth: Same but auth_enabled=True
  - seed_launch:          Factory to populate launch_info in Redis
"""

from __future__ import annotations

import sys
from collections.abc import AsyncGenerator
from unittest.mock import patch

import fakeredis
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ltt.models.base import Base

# Prevent api/__init__.py from eagerly importing api.app (which pulls in
# langchain_anthropic and the entire agent stack).  We install a fake 'api'
# package entry so that submodule imports like 'api.settings' resolve their
# parent without triggering __init__.py's top-level import.
import types as _types

if "api" not in sys.modules:
    sys.modules["api"] = _types.ModuleType("api")
    sys.modules["api"].__path__ = [  # type: ignore[attr-defined]
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "src"
        / "api"
    ].__str__()
    # __path__ must be a list of strings for the import machinery
    _api_src = str(
        __import__("pathlib").Path(__file__).resolve().parents[1] / "src" / "api"
    )
    sys.modules["api"].__path__ = [_api_src]  # type: ignore[attr-defined]

from api.settings import Settings, clear_settings_cache  # noqa: E402
from api.lti.storage import RedisLaunchDataStorage  # noqa: E402

TEST_DATABASE_URL = (
    "postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_test"
)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def test_settings() -> Settings:
    clear_settings_cache()
    return Settings(
        env="local",
        database_url=TEST_DATABASE_URL,
        redis_url="redis://fake",
        auth_enabled=False,
        debug=True,
        dev_learner_id="learner-test-001",
        dev_project_id="proj-test",
        frontend_url="http://localhost:3000",
        lti_platform_config="configs/lti/platform.json",
        lti_private_key="configs/lti/private.key",
        lti_public_key="configs/lti/public.key",
        checkpoint_database_url="",
        anthropic_api_key="",
    )


@pytest.fixture(scope="function")
def test_settings_auth(test_settings: Settings) -> Settings:
    clear_settings_cache()
    return Settings(**{**test_settings.model_dump(), "auth_enabled": True})


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def session_factory(
    async_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def fake_redis_client() -> fakeredis.FakeRedis:
    server = fakeredis.FakeServer()
    return fakeredis.FakeRedis(server=server, decode_responses=True)


@pytest.fixture(scope="function")
def lti_storage(fake_redis_client: fakeredis.FakeRedis) -> RedisLaunchDataStorage:
    return RedisLaunchDataStorage(fake_redis_client)


# ---------------------------------------------------------------------------
# FastAPI app builder
# ---------------------------------------------------------------------------


def _build_test_app(
    settings: Settings,
    engine: AsyncEngine,
    sf: async_sessionmaker[AsyncSession],
    storage: RedisLaunchDataStorage,
):
    """Build a FastAPI app with patched singletons (no real lifespan)."""
    from fastapi import FastAPI

    from api.database import _engine, _session_factory  # noqa: F401
    import api.database as db_mod
    import api.lti.routes as lti_routes_mod
    from api.frontend_routes import router as frontend_router
    from api.lti.routes import router as lti_router

    # Patch module-level singletons
    db_mod._engine = engine
    db_mod._session_factory = sf
    lti_routes_mod._launch_data_storage = storage

    test_app = FastAPI(title="Test")

    # Only include routers that don't pull in the agent stack
    test_app.include_router(frontend_router)  # has its own /api/v1 prefix
    test_app.include_router(lti_router)  # has its own /lti prefix

    @test_app.get("/health")
    async def health():
        return {"status": "healthy"}

    return test_app


# ---------------------------------------------------------------------------
# FastAPI app (auth_enabled=False)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def app(
    test_settings: Settings,
    async_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    lti_storage: RedisLaunchDataStorage,
) -> AsyncGenerator:
    with patch("api.settings.get_settings", return_value=test_settings), \
         patch("api.auth.get_settings", return_value=test_settings), \
         patch("api.lti.routes.get_settings", return_value=test_settings):
        test_app = _build_test_app(
            test_settings, async_engine, session_factory, lti_storage
        )
        yield test_app
    clear_settings_cache()


@pytest_asyncio.fixture(scope="function")
async def client(app) -> AsyncGenerator:
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# FastAPI app (auth_enabled=True)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def app_auth(
    test_settings_auth: Settings,
    async_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    lti_storage: RedisLaunchDataStorage,
) -> AsyncGenerator:
    with patch("api.settings.get_settings", return_value=test_settings_auth), \
         patch("api.auth.get_settings", return_value=test_settings_auth), \
         patch("api.lti.routes.get_settings", return_value=test_settings_auth):
        test_app = _build_test_app(
            test_settings_auth, async_engine, session_factory, lti_storage
        )
        yield test_app
    clear_settings_cache()


@pytest_asyncio.fixture(scope="function")
async def client_auth(app_auth) -> AsyncGenerator:
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Convenience: seed a launch session in Redis
# ---------------------------------------------------------------------------


@pytest.fixture
def seed_launch(lti_storage: RedisLaunchDataStorage):
    """Factory fixture: seed_launch(launch_id, learner_id, ...) → launch_id."""

    def _seed(
        launch_id: str = "test-launch-001",
        learner_id: str = "learner-test-001",
        project_id: str = "proj-test",
        roles: list[str] | None = None,
        **extras,
    ) -> str:
        data = {
            "sub": f"sub-{learner_id}",
            "iss": "https://test-platform.example.com",
            "email": "test@example.com",
            "name": "Test User",
            "learner_id": learner_id,
            "project_id": project_id,
            "workspace_type": "sql",
            "roles": roles or [],
            "context": {},
            "resource_link": {},
            "tool_platform": {},
            "ags": {},
            "custom": {"project_id": project_id},
            **extras,
        }
        lti_storage.set_value(f"launch_info:{launch_id}", data, exp=3600)
        return launch_id

    return _seed
