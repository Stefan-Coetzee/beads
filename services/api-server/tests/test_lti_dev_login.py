"""Tests for the dev login/logout flow (/lti/dev/login, /lti/dev/logout)."""

from ltt.models.learner import LearnerModel
from sqlalchemy import select


class TestDevLogin:
    async def test_dev_login_creates_session(self, client, lti_storage):
        """Dev login returns launch_id and stores session in Redis."""
        resp = await client.post(
            "/lti/dev/login",
            json={"learner_id": "learner-dev-001", "project_id": "proj-dev"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "launch_id" in data
        assert data["learner_id"] == "learner-dev-001"
        assert data["project_id"] == "proj-dev"

        launch_info = lti_storage.get_value(f"launch_info:{data['launch_id']}")
        assert launch_info is not None
        assert launch_info["learner_id"] == "learner-dev-001"
        assert launch_info["iss"] == "http://localhost"

    async def test_dev_login_creates_learner_in_db(self, client, async_session):
        """Dev login creates the learner record if it doesn't exist."""
        resp = await client.post(
            "/lti/dev/login",
            json={"learner_id": "learner-new-dev", "project_id": ""},
        )
        assert resp.status_code == 200

        # Re-query from a fresh session to see committed data
        result = await async_session.execute(
            select(LearnerModel).where(LearnerModel.id == "learner-new-dev")
        )
        learner = result.scalar_one_or_none()
        assert learner is not None

    async def test_dev_login_uses_default_learner_id(self, client, test_settings):
        """Omitting learner_id uses settings.dev_learner_id."""
        resp = await client.post("/lti/dev/login", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["learner_id"] == test_settings.dev_learner_id

    async def test_dev_login_idempotent(self, client):
        """Calling dev login twice for same learner_id doesn't fail."""
        for _ in range(2):
            resp = await client.post(
                "/lti/dev/login",
                json={"learner_id": "learner-repeat"},
            )
            assert resp.status_code == 200

    async def test_dev_login_blocked_when_auth_enabled(self, client_auth):
        """Dev login returns 404 when auth_enabled=True."""
        resp = await client_auth.post("/lti/dev/login", json={"learner_id": "x"})
        assert resp.status_code == 404

    async def test_dev_login_session_usable_for_api(self, client):
        """Launch_id from dev login can be used as X-LTI-Launch-Id header."""
        login_resp = await client.post("/lti/dev/login", json={"learner_id": "learner-api-test"})
        launch_id = login_resp.json()["launch_id"]

        ctx_resp = await client.get(
            "/lti/debug/context",
            headers={"X-LTI-Launch-Id": launch_id},
        )
        assert ctx_resp.status_code == 200
        data = ctx_resp.json()
        assert data["data"]["learner_id"] == "learner-api-test"


class TestDevLogout:
    async def test_dev_logout_clears_session(self, client, lti_storage):
        """Logout deletes the launch_info key from Redis."""
        login_resp = await client.post("/lti/dev/login", json={"learner_id": "learner-logout-test"})
        launch_id = login_resp.json()["launch_id"]
        assert lti_storage.get_value(f"launch_info:{launch_id}") is not None

        logout_resp = await client.post(
            "/lti/dev/logout",
            headers={"X-LTI-Launch-Id": launch_id},
        )
        assert logout_resp.status_code == 200
        assert logout_resp.json()["ok"] is True
        assert lti_storage.get_value(f"launch_info:{launch_id}") is None

    async def test_dev_logout_without_header(self, client):
        """Logout without X-LTI-Launch-Id returns ok=false."""
        resp = await client.post("/lti/dev/logout")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False

    async def test_dev_logout_blocked_when_auth_enabled(self, client_auth):
        """Dev logout returns 404 when auth_enabled=True."""
        resp = await client_auth.post(
            "/lti/dev/logout",
            headers={"X-LTI-Launch-Id": "any"},
        )
        assert resp.status_code == 404
