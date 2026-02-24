"""Tests for api.auth.get_learner_context dependency."""


class TestGetLearnerContextDevMode:
    """Auth with auth_enabled=False (dev mode)."""

    async def test_no_header_returns_dev_fallback(self, client):
        """No X-LTI-Launch-Id header -> dev context (not 401)."""
        resp = await client.get("/api/v1/projects")
        assert resp.status_code != 401

    async def test_valid_launch_id_resolves_from_redis(self, client, seed_launch):
        """Valid launch_id resolves learner from Redis."""
        launch_id = seed_launch(
            launch_id="auth-test-001",
            learner_id="learner-redis-001",
            project_id="proj-alpha",
        )
        resp = await client.get(
            "/lti/debug/context",
            headers={"X-LTI-Launch-Id": launch_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["learner_id"] == "learner-redis-001"

    async def test_invalid_launch_id_falls_back_to_dev(self, client):
        """Invalid launch_id + auth_enabled=False -> no 401."""
        # debug/context does its own lookup, so it returns an error message
        # but the endpoint itself is accessible (not 401)
        resp = await client.get(
            "/lti/debug/context",
            headers={"X-LTI-Launch-Id": "nonexistent-launch"},
        )
        assert resp.status_code == 200
        assert "No launch data" in resp.json()["error"]

    async def test_instructor_role_detected(self, client, seed_launch):
        """Instructor roles in launch data are surfaced."""
        launch_id = seed_launch(
            launch_id="instructor-test",
            learner_id="learner-instructor",
            roles=[
                "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor",
            ],
        )
        resp = await client.get(
            "/lti/debug/context",
            headers={"X-LTI-Launch-Id": launch_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        roles = data["data"]["roles"]
        assert any("Instructor" in r for r in roles)


class TestGetLearnerContextAuthEnabled:
    """Auth with auth_enabled=True."""

    async def test_no_header_returns_401(self, client_auth):
        """Missing header -> 401 for auth-protected endpoint."""
        resp = await client_auth.get("/api/v1/project/proj-xxx/tree")
        assert resp.status_code == 401
        assert "Missing X-LTI-Launch-Id" in resp.json()["detail"]

    async def test_expired_launch_id_returns_401(self, client_auth):
        """Launch ID not in Redis -> 401."""
        resp = await client_auth.get(
            "/api/v1/project/proj-xxx/tree",
            headers={"X-LTI-Launch-Id": "expired-launch-id"},
        )
        assert resp.status_code == 401
        assert "expired or invalid" in resp.json()["detail"]

    async def test_valid_launch_id_succeeds(self, client_auth, seed_launch):
        """Valid launch ID with auth enabled doesn't return 401."""
        launch_id = seed_launch(launch_id="auth-enabled-test")
        resp = await client_auth.get(
            "/api/v1/project/proj-nonexistent/tree",
            headers={"X-LTI-Launch-Id": launch_id},
        )
        # Should be 404 (project not found), NOT 401
        assert resp.status_code != 401
