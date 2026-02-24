"""Tests for auth-protected API endpoints.

Verifies that endpoints behind Depends(get_learner_context) correctly
reject unauthorized requests and accept authorized ones.
"""


class TestAuthBoundary:
    """Endpoints that require auth return 401 when auth_enabled=True."""

    async def test_project_tree_requires_auth(self, client_auth):
        resp = await client_auth.get("/api/v1/project/proj-x/tree")
        assert resp.status_code == 401

    async def test_task_details_requires_auth(self, client_auth):
        resp = await client_auth.get("/api/v1/task/task-x")
        assert resp.status_code == 401

    async def test_start_task_requires_auth(self, client_auth):
        resp = await client_auth.post("/api/v1/task/task-x/start")
        assert resp.status_code == 401

    async def test_ready_tasks_requires_auth(self, client_auth):
        resp = await client_auth.get("/api/v1/project/proj-x/ready")
        assert resp.status_code == 401

    async def test_valid_auth_passes_through(self, client_auth, seed_launch):
        """With valid auth, endpoints return 404 (not 401) for missing data."""
        launch_id = seed_launch(launch_id="boundary-test")
        resp = await client_auth.get(
            "/api/v1/project/proj-nonexistent/tree",
            headers={"X-LTI-Launch-Id": launch_id},
        )
        assert resp.status_code != 401


class TestPublicEndpoints:
    """Endpoints that don't require auth work regardless."""

    async def test_health_always_accessible(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    async def test_health_with_auth_enabled(self, client_auth):
        resp = await client_auth.get("/health")
        assert resp.status_code == 200

    async def test_projects_list_no_auth(self, client_auth):
        """GET /api/v1/projects has no auth dependency."""
        resp = await client_auth.get("/api/v1/projects")
        assert resp.status_code != 401
