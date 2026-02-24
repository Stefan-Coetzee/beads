"""Tests for the LTI 1.3 OIDC login and launch endpoints.

Patches FastAPIMessageLaunch to skip JWT crypto while testing the rest
of the launch handler (user mapping, Redis storage, redirect generation).
"""

import re
from unittest.mock import patch, MagicMock

from sqlalchemy import select
from starlette.responses import RedirectResponse

from ltt.models.lti_mapping import LTIUserMapping
from ltt.models.lti_launch import LTILaunch
from ltt.models.learner import LearnerModel
from ltt.utils.ids import generate_entity_id


def _mock_launch_data(
    sub="test-user-sub",
    iss="https://imbizo.alx-ai-tools.com",
    name=None,
    email=None,
    project_id="proj-test-001",
    workspace_type="sql",
    roles=None,
    ags_endpoint=None,
    custom_extra=None,
):
    """Build a mock launch_data dict mirroring what PyLTI1p3 returns."""
    custom = {"project_id": project_id, "workspace_type": workspace_type}
    if custom_extra:
        custom.update(custom_extra)

    data = {
        "sub": sub,
        "iss": iss,
        "https://purl.imsglobal.org/spec/lti/claim/custom": custom,
        "https://purl.imsglobal.org/spec/lti/claim/roles": roles or [
            "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner",
        ],
        "https://purl.imsglobal.org/spec/lti/claim/context": {
            "id": "course-v1:Test+101+2024",
        },
        "https://purl.imsglobal.org/spec/lti/claim/resource_link": {
            "id": "resource-001",
        },
        "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": ags_endpoint or {},
        "https://purl.imsglobal.org/spec/lti/claim/lis": {},
        "https://purl.imsglobal.org/spec/lti/claim/tool_platform": {},
    }
    if name:
        data["name"] = name
    if email:
        data["email"] = email
    return data


class TestLtiLogin:

    async def test_login_post_redirects(self, client):
        """POST /lti/login with valid params returns a redirect."""
        with patch("api.lti.routes.FastAPIOIDCLogin") as MockOIDCLogin:
            mock_instance = MockOIDCLogin.return_value
            mock_instance.redirect.return_value = RedirectResponse(
                url="https://platform.example.com/auth?state=abc",
                status_code=302,
            )
            resp = await client.post(
                "/lti/login",
                data={
                    "iss": "https://imbizo.alx-ai-tools.com",
                    "login_hint": "user123",
                    "target_link_uri": "http://localhost:8000/lti/launch",
                },
            )
            assert resp.status_code == 302
            assert "platform.example.com" in resp.headers.get("location", "")

    async def test_login_missing_target_link_uri(self, client):
        """POST /lti/login without target_link_uri returns 400."""
        with patch("api.lti.routes.FastAPIOIDCLogin") as MockOIDCLogin:
            mock_instance = MockOIDCLogin.return_value
            # Simulate OIDCLogin processing with missing target_link_uri
            resp = await client.post(
                "/lti/login",
                data={"iss": "https://example.com", "login_hint": "user123"},
            )
            assert resp.status_code == 400
            assert "target_link_uri" in resp.json()["detail"]

    async def test_login_get_method_works(self, client):
        """GET /lti/login also works."""
        with patch("api.lti.routes.FastAPIOIDCLogin") as MockOIDCLogin:
            mock_instance = MockOIDCLogin.return_value
            mock_instance.redirect.return_value = RedirectResponse(
                url="https://platform.example.com/auth", status_code=302
            )
            resp = await client.get(
                "/lti/login",
                params={
                    "iss": "https://imbizo.alx-ai-tools.com",
                    "login_hint": "user123",
                    "target_link_uri": "http://localhost:8000/lti/launch",
                },
            )
            assert resp.status_code == 302


class TestLtiLaunch:

    async def test_launch_creates_learner_and_redirects(
        self, client, async_session, lti_storage
    ):
        """Successful launch creates learner, stores Redis, redirects."""
        with patch("api.lti.routes.FastAPIMessageLaunch") as MockLaunch:
            mock = MockLaunch.return_value
            mock.get_launch_data.return_value = _mock_launch_data(
                sub="platform-user-42",
                name="Alice Smith",
                email="alice@example.com",
            )
            mock.get_launch_id.return_value = "mock-launch-001"
            mock.is_deep_link_launch.return_value = False
            mock.has_nrps.return_value = False

            resp = await client.post(
                "/lti/launch",
                data={"id_token": "fake.jwt", "state": "mock-state"},
                follow_redirects=False,
            )

        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "localhost:3000" in location
        assert "workspace/proj-test-001" in location
        assert "launch_id=mock-launch-001" in location
        assert "lti=1" in location
        assert "instructor=0" in location

        # Verify learner mapping in DB
        result = await async_session.execute(
            select(LTIUserMapping).where(
                LTIUserMapping.lti_sub == "platform-user-42"
            )
        )
        mapping = result.scalar_one_or_none()
        assert mapping is not None
        assert mapping.name == "Alice Smith"

        # Verify Redis
        launch_info = lti_storage.get_value("launch_info:mock-launch-001")
        assert launch_info is not None
        assert launch_info["sub"] == "platform-user-42"

    async def test_launch_instructor_flag(self, client):
        """Instructor role sets instructor=1 in redirect URL."""
        with patch("api.lti.routes.FastAPIMessageLaunch") as MockLaunch:
            mock = MockLaunch.return_value
            mock.get_launch_data.return_value = _mock_launch_data(
                sub="instructor-sub",
                roles=[
                    "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor",
                ],
            )
            mock.get_launch_id.return_value = "instructor-launch"
            mock.is_deep_link_launch.return_value = False
            mock.has_nrps.return_value = False

            resp = await client.post(
                "/lti/launch",
                data={"id_token": "x", "state": "y"},
                follow_redirects=False,
            )
        assert "instructor=1" in resp.headers["location"]

    async def test_launch_existing_learner_reuses_mapping(
        self, client, async_session
    ):
        """Second launch for same sub+iss reuses the same learner_id."""
        learner_id = "learner-existing-001"
        async_session.add(LearnerModel(id=learner_id, learner_metadata="{}"))
        async_session.add(LTIUserMapping(
            id=generate_entity_id("lti"),
            lti_sub="returning-user",
            lti_iss="https://imbizo.alx-ai-tools.com",
            learner_id=learner_id,
            name="Old Name",
        ))
        await async_session.commit()

        with patch("api.lti.routes.FastAPIMessageLaunch") as MockLaunch:
            mock = MockLaunch.return_value
            mock.get_launch_data.return_value = _mock_launch_data(
                sub="returning-user",
                name="Updated Name",
                email="updated@example.com",
            )
            mock.get_launch_id.return_value = "return-launch"
            mock.is_deep_link_launch.return_value = False
            mock.has_nrps.return_value = False

            resp = await client.post(
                "/lti/launch",
                data={"id_token": "x", "state": "y"},
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert f"learnerId={learner_id}" in resp.headers["location"]

    async def test_launch_persists_lti_launch_record(
        self, client, async_session, lti_storage
    ):
        """Launch persists an LTILaunch record in DB for grade passback."""
        with patch("api.lti.routes.FastAPIMessageLaunch") as MockLaunch:
            mock = MockLaunch.return_value
            mock.get_launch_data.return_value = _mock_launch_data(
                sub="persist-user",
                project_id="proj-persist",
                ags_endpoint={
                    "lineitems": "https://platform.example.com/lineitems",
                    "scope": ["https://purl.imsglobal.org/spec/lti-ags/scope/score"],
                },
            )
            mock.get_launch_id.return_value = "persist-launch-001"
            mock.is_deep_link_launch.return_value = False
            mock.has_nrps.return_value = False

            await client.post(
                "/lti/launch",
                data={"id_token": "x", "state": "y"},
                follow_redirects=False,
            )

        launch = await async_session.get(LTILaunch, "persist-launch-001")
        assert launch is not None
        assert launch.lti_sub == "persist-user"
        assert launch.ags_lineitems == "https://platform.example.com/lineitems"

    async def test_launch_caches_active_mapping(self, client, lti_storage):
        """Launch stores active:{learner_id}:{project_id} in Redis."""
        with patch("api.lti.routes.FastAPIMessageLaunch") as MockLaunch:
            mock = MockLaunch.return_value
            mock.get_launch_data.return_value = _mock_launch_data(
                sub="cache-user",
                project_id="proj-cache",
            )
            mock.get_launch_id.return_value = "cache-launch"
            mock.is_deep_link_launch.return_value = False
            mock.has_nrps.return_value = False

            resp = await client.post(
                "/lti/launch",
                data={"id_token": "x", "state": "y"},
                follow_redirects=False,
            )

        location = resp.headers["location"]
        learner_match = re.search(r"learnerId=(learner-[a-z0-9]+)", location)
        assert learner_match
        learner_id = learner_match.group(1)

        active = lti_storage.get_value(f"active:{learner_id}:proj-cache")
        assert active is not None
        assert active["launch_id"] == "cache-launch"

    async def test_launch_unsubstituted_vars_filtered(self, client):
        """Un-substituted LTI vars like $Person.name.full are treated as None."""
        with patch("api.lti.routes.FastAPIMessageLaunch") as MockLaunch:
            mock = MockLaunch.return_value
            mock.get_launch_data.return_value = _mock_launch_data(
                sub="unsub-user",
                name="$Person.name.full",
                email="$Person.email.primary",
                custom_extra={
                    "user_name": "$Person.name.full",
                    "user_email": "$Person.email.primary",
                },
            )
            mock.get_launch_id.return_value = "unsub-launch"
            mock.is_deep_link_launch.return_value = False
            mock.has_nrps.return_value = False

            resp = await client.post(
                "/lti/launch",
                data={"id_token": "x", "state": "y"},
                follow_redirects=False,
            )
        # Should succeed (redirect) even with unsubstituted vars
        assert resp.status_code == 302
