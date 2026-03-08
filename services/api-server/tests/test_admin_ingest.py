"""
Tests for POST /api/v1/projects/ingest admin endpoint.

Covers:
- Auth: missing key, wrong key, disabled endpoint, valid key
- Input: JSON body, file upload, empty body
- Validation: descriptive error messages, dry-run mode
- Ingestion: success, duplicate detection, version bump
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import pytest_asyncio
from api.settings import Settings, clear_settings_cache
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from .conftest import _build_test_app

ADMIN_KEY = "test-admin-key-12345"
INGEST_URL = "/api/v1/projects/ingest"

MINIMAL_PROJECT = {
    "project_id": "test-project",
    "title": "Test Project",
    "description": "A test project",
    "version": 1,
    "epics": [],
}

PROJECT_WITH_TASKS = {
    "project_id": "tasks-project",
    "title": "Project With Tasks",
    "description": "Has epics and tasks",
    "version": 1,
    "workspace_type": "sql",
    "learning_objectives": [
        {"level": "apply", "description": "Learn SQL basics"},
    ],
    "epics": [
        {
            "title": "Epic 1",
            "description": "First epic",
            "tasks": [
                {
                    "title": "Task 1",
                    "description": "First task",
                    "acceptance_criteria": "- Works",
                    "subtasks": [
                        {
                            "title": "Subtask 1",
                            "description": "First subtask",
                            "acceptance_criteria": "- Done",
                        },
                    ],
                },
                {
                    "title": "Task 2",
                    "description": "Second task",
                    "dependencies": ["Task 1"],
                },
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def admin_settings() -> Settings:
    clear_settings_cache()
    from .conftest import TEST_DATABASE_URL

    return Settings(
        env="local",
        database_url=TEST_DATABASE_URL,
        redis_url="redis://fake",
        auth_enabled=False,
        debug=True,
        admin_api_key=ADMIN_KEY,
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
def no_admin_settings() -> Settings:
    """Settings with admin_api_key empty (disabled)."""
    clear_settings_cache()
    from .conftest import TEST_DATABASE_URL

    return Settings(
        env="local",
        database_url=TEST_DATABASE_URL,
        redis_url="redis://fake",
        auth_enabled=False,
        debug=True,
        admin_api_key="",
        dev_learner_id="learner-test-001",
        dev_project_id="proj-test",
        frontend_url="http://localhost:3000",
        lti_platform_config="configs/lti/platform.json",
        lti_private_key="configs/lti/private.key",
        lti_public_key="configs/lti/public.key",
        checkpoint_database_url="",
        anthropic_api_key="",
    )


@pytest_asyncio.fixture(scope="function")
async def admin_client(
    admin_settings: Settings,
    async_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    lti_storage,
) -> AsyncClient:
    with (
        patch("api.settings.get_settings", return_value=admin_settings),
        patch("api.auth.get_settings", return_value=admin_settings),
        patch("api.lti.routes.get_settings", return_value=admin_settings),
    ):
        test_app = _build_test_app(admin_settings, async_engine, session_factory, lti_storage)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    clear_settings_cache()


@pytest_asyncio.fixture(scope="function")
async def no_admin_client(
    no_admin_settings: Settings,
    async_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    lti_storage,
) -> AsyncClient:
    with (
        patch("api.settings.get_settings", return_value=no_admin_settings),
        patch("api.auth.get_settings", return_value=no_admin_settings),
        patch("api.lti.routes.get_settings", return_value=no_admin_settings),
    ):
        test_app = _build_test_app(no_admin_settings, async_engine, session_factory, lti_storage)
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    clear_settings_cache()


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_api_key(admin_client: AsyncClient):
    """Request without X-Admin-API-Key header → 401."""
    resp = await admin_client.post(INGEST_URL, json=MINIMAL_PROJECT)
    assert resp.status_code == 401
    assert "Missing" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_wrong_api_key(admin_client: AsyncClient):
    """Request with wrong key → 403."""
    resp = await admin_client.post(
        INGEST_URL,
        json=MINIMAL_PROJECT,
        headers={"X-Admin-API-Key": "wrong-key"},
    )
    assert resp.status_code == 403
    assert "Invalid" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_disabled(no_admin_client: AsyncClient):
    """When admin_api_key is empty, endpoint returns 503."""
    resp = await no_admin_client.post(
        INGEST_URL,
        json=MINIMAL_PROJECT,
        headers={"X-Admin-API-Key": "anything"},
    )
    assert resp.status_code == 503
    assert "disabled" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_valid_key_accepted(admin_client: AsyncClient):
    """Valid key → proceeds to ingestion (2xx)."""
    resp = await admin_client.post(
        INGEST_URL,
        json=MINIMAL_PROJECT,
        headers={"X-Admin-API-Key": ADMIN_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == "test-project"
    assert data["title"] == "Test Project"


# ---------------------------------------------------------------------------
# Input format tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_json_body(admin_client: AsyncClient):
    """JSON body ingestion works."""
    resp = await admin_client.post(
        INGEST_URL,
        json=MINIMAL_PROJECT,
        headers={"X-Admin-API-Key": ADMIN_KEY},
    )
    assert resp.status_code == 200
    assert resp.json()["internal_id"].startswith("proj-")


@pytest.mark.asyncio
async def test_file_upload(admin_client: AsyncClient):
    """Multipart file upload ingestion works."""
    import json

    project = {**MINIMAL_PROJECT, "project_id": "upload-test"}
    resp = await admin_client.post(
        INGEST_URL,
        files={"file": ("project.json", json.dumps(project).encode(), "application/json")},
        headers={"X-Admin-API-Key": ADMIN_KEY},
    )
    assert resp.status_code == 200
    assert resp.json()["project_id"] == "upload-test"


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_title(admin_client: AsyncClient):
    """Missing required field → 422 with descriptive error."""
    bad_project = {"project_id": "bad-proj", "version": 1}
    resp = await admin_client.post(
        INGEST_URL,
        json=bad_project,
        headers={"X-Admin-API-Key": ADMIN_KEY},
    )
    assert resp.status_code == 422
    errors = resp.json()["detail"]["errors"]
    assert any("title" in e for e in errors)


@pytest.mark.asyncio
async def test_invalid_bloom_level(admin_client: AsyncClient):
    """Invalid Bloom level → 422 with specific error."""
    bad_project = {
        "project_id": "bad-bloom",
        "title": "Bad Bloom",
        "version": 1,
        "learning_objectives": [
            {"level": "memorize", "description": "This uses a wrong bloom level"},
        ],
    }
    resp = await admin_client.post(
        INGEST_URL,
        json=bad_project,
        headers={"X-Admin-API-Key": ADMIN_KEY},
    )
    assert resp.status_code == 422
    errors = resp.json()["detail"]["errors"]
    assert any("memorize" in e and "Bloom" in e for e in errors)


@pytest.mark.asyncio
async def test_invalid_dependency_reference(admin_client: AsyncClient):
    """Dependency referencing non-existent task → descriptive error."""
    bad_project = {
        "project_id": "bad-deps",
        "title": "Bad Dependencies",
        "version": 1,
        "epics": [
            {
                "title": "Epic 1",
                "tasks": [
                    {
                        "title": "Task 1",
                        "dependencies": ["Nonexistent Task"],
                    },
                ],
            },
        ],
    }
    resp = await admin_client.post(
        INGEST_URL,
        json=bad_project,
        headers={"X-Admin-API-Key": ADMIN_KEY},
    )
    assert resp.status_code == 422
    errors = resp.json()["detail"]["errors"]
    assert any("Nonexistent Task" in e and "does not exist" in e for e in errors)


@pytest.mark.asyncio
async def test_invalid_slug_format(admin_client: AsyncClient):
    """Invalid project_id slug format → descriptive error."""
    bad_project = {
        "project_id": "BAD SLUG!!",
        "title": "Bad Slug",
        "version": 1,
    }
    resp = await admin_client.post(
        INGEST_URL,
        json=bad_project,
        headers={"X-Admin-API-Key": ADMIN_KEY},
    )
    assert resp.status_code == 422
    errors = resp.json()["detail"]["errors"]
    assert any("invalid" in e.lower() and "BAD SLUG!!" in e for e in errors)


# ---------------------------------------------------------------------------
# Dry-run tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_valid(admin_client: AsyncClient):
    """Dry-run of valid project → valid=True, no DB changes."""
    resp = await admin_client.post(
        f"{INGEST_URL}?dry_run=true",
        json=PROJECT_WITH_TASKS,
        headers={"X-Admin-API-Key": ADMIN_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["task_count"] > 0
    assert data["objective_count"] > 0
    assert data["errors"] == []

    # Verify nothing was persisted
    resp2 = await admin_client.get("/api/v1/projects/tasks-project")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_dry_run_invalid(admin_client: AsyncClient):
    """Dry-run of invalid project → valid=False with errors."""
    bad_project = {"version": 1}
    resp = await admin_client.post(
        f"{INGEST_URL}?dry_run=true",
        json=bad_project,
        headers={"X-Admin-API-Key": ADMIN_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0


# ---------------------------------------------------------------------------
# Ingestion + duplicate detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_ingestion(admin_client: AsyncClient):
    """Full ingestion creates project and returns expected fields."""
    resp = await admin_client.post(
        INGEST_URL,
        json=PROJECT_WITH_TASKS,
        headers={"X-Admin-API-Key": ADMIN_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == "tasks-project"
    assert data["internal_id"].startswith("proj-")
    assert data["version"] == 1
    assert data["title"] == "Project With Tasks"
    assert data["task_count"] >= 5  # project + epic + 2 tasks + 1 subtask
    assert data["objective_count"] >= 1


@pytest.mark.asyncio
async def test_auto_version_on_reingest(admin_client: AsyncClient):
    """Re-ingesting same slug auto-increments version instead of rejecting."""
    # First ingest → version 1
    resp1 = await admin_client.post(
        INGEST_URL,
        json=MINIMAL_PROJECT,
        headers={"X-Admin-API-Key": ADMIN_KEY},
    )
    assert resp1.status_code == 200
    assert resp1.json()["version"] == 1

    # Same payload again → auto-bumped to version 2
    resp2 = await admin_client.post(
        INGEST_URL,
        json=MINIMAL_PROJECT,
        headers={"X-Admin-API-Key": ADMIN_KEY},
    )
    assert resp2.status_code == 200
    assert resp2.json()["version"] == 2

    # Third time → version 3
    resp3 = await admin_client.post(
        INGEST_URL,
        json=MINIMAL_PROJECT,
        headers={"X-Admin-API-Key": ADMIN_KEY},
    )
    assert resp3.status_code == 200
    assert resp3.json()["version"] == 3
