"""Tests for LTI debug endpoints (only available when DEBUG=true)."""


class TestDebugContext:
    async def test_returns_launch_data(self, client, seed_launch):
        """GET /lti/debug/context returns stored launch data."""
        launch_id = seed_launch(
            launch_id="debug-ctx-001",
            learner_id="learner-dbg",
        )
        resp = await client.get(
            "/lti/debug/context",
            headers={"X-LTI-Launch-Id": launch_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["launch_id"] == launch_id
        assert data["data"]["learner_id"] == "learner-dbg"

    async def test_missing_header_returns_error(self, client):
        """Missing header returns error message (not 401)."""
        resp = await client.get("/lti/debug/context")
        assert resp.status_code == 200
        assert "error" in resp.json()

    async def test_invalid_launch_id_returns_error(self, client):
        """Unknown launch_id returns 'No launch data' error."""
        resp = await client.get(
            "/lti/debug/context",
            headers={"X-LTI-Launch-Id": "nonexistent"},
        )
        assert resp.status_code == 200
        assert "No launch data" in resp.json()["error"]


class TestDebugHealth:
    async def test_health_checks_redis(self, client):
        """Health check reports Redis status."""
        resp = await client.get("/lti/debug/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "checks" in data
        assert data["checks"]["redis"]["ok"] is True

    async def test_health_without_launch_id(self, client):
        """Without launch_id, AGS shows 'no launch session'."""
        resp = await client.get("/lti/debug/health")
        data = resp.json()
        assert data["checks"]["ags"]["ok"] is None
        assert "no launch session" in data["checks"]["ags"]["detail"]

    async def test_health_with_launch_id_pii(self, client, seed_launch):
        """With valid launch_id + PII, pii check is OK."""
        launch_id = seed_launch(
            launch_id="health-test",
            name="Health User",
            email="health@test.com",
        )
        resp = await client.get(
            "/lti/debug/health",
            headers={"X-LTI-Launch-Id": launch_id},
        )
        data = resp.json()
        assert data["checks"]["pii"]["ok"] is True
