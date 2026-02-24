"""Tests for api.lti.users (LTI user -> LTT learner mapping)."""

from api.lti.users import get_learner_by_lti, get_or_create_lti_learner
from ltt.models.learner import LearnerModel
from ltt.models.lti_mapping import LTIUserMapping
from sqlalchemy import select


class TestGetOrCreateLtiLearner:
    async def test_creates_new_learner_on_first_launch(self, async_session):
        """First LTI launch creates a new learner and mapping."""
        learner_id = await get_or_create_lti_learner(
            async_session,
            lti_sub="new-sub-001",
            lti_iss="https://platform.example.com",
            name="New User",
            email="new@example.com",
        )
        assert learner_id.startswith("learner-")

        learner = await async_session.get(LearnerModel, learner_id)
        assert learner is not None

        result = await async_session.execute(
            select(LTIUserMapping).where(LTIUserMapping.lti_sub == "new-sub-001")
        )
        mapping = result.scalar_one()
        assert mapping.learner_id == learner_id
        assert mapping.name == "New User"
        assert mapping.email == "new@example.com"

    async def test_returns_existing_learner_on_repeat_launch(self, async_session):
        """Repeat launch returns the same learner_id."""
        first_id = await get_or_create_lti_learner(
            async_session,
            lti_sub="repeat-sub",
            lti_iss="https://platform.example.com",
        )
        second_id = await get_or_create_lti_learner(
            async_session,
            lti_sub="repeat-sub",
            lti_iss="https://platform.example.com",
        )
        assert first_id == second_id

    async def test_updates_name_and_email_on_repeat(self, async_session):
        """Repeat launch updates cached PII if changed."""
        await get_or_create_lti_learner(
            async_session,
            lti_sub="update-sub",
            lti_iss="https://platform.example.com",
            name="Old Name",
            email="old@example.com",
        )
        await get_or_create_lti_learner(
            async_session,
            lti_sub="update-sub",
            lti_iss="https://platform.example.com",
            name="New Name",
            email="new@example.com",
        )

        result = await async_session.execute(
            select(LTIUserMapping).where(LTIUserMapping.lti_sub == "update-sub")
        )
        mapping = result.scalar_one()
        assert mapping.name == "New Name"
        assert mapping.email == "new@example.com"

    async def test_does_not_overwrite_name_with_none(self, async_session):
        """None values don't overwrite existing PII."""
        await get_or_create_lti_learner(
            async_session,
            lti_sub="keep-sub",
            lti_iss="https://platform.example.com",
            name="Keep This",
            email="keep@example.com",
        )
        await get_or_create_lti_learner(
            async_session,
            lti_sub="keep-sub",
            lti_iss="https://platform.example.com",
            name=None,
            email=None,
        )

        result = await async_session.execute(
            select(LTIUserMapping).where(LTIUserMapping.lti_sub == "keep-sub")
        )
        mapping = result.scalar_one()
        assert mapping.name == "Keep This"
        assert mapping.email == "keep@example.com"

    async def test_different_iss_creates_separate_learner(self, async_session):
        """Same sub but different iss = different learner."""
        id_a = await get_or_create_lti_learner(
            async_session,
            lti_sub="shared-sub",
            lti_iss="https://platform-a.com",
        )
        id_b = await get_or_create_lti_learner(
            async_session,
            lti_sub="shared-sub",
            lti_iss="https://platform-b.com",
        )
        assert id_a != id_b

    async def test_handles_none_name_and_email(self, async_session):
        """Creating with no PII stores None in mapping."""
        learner_id = await get_or_create_lti_learner(
            async_session,
            lti_sub="no-pii-sub",
            lti_iss="https://platform.example.com",
        )
        assert learner_id.startswith("learner-")


class TestGetLearnerByLti:
    async def test_returns_none_for_unknown(self, async_session):
        """Unknown sub+iss returns None."""
        result = await get_learner_by_lti(
            async_session,
            lti_sub="unknown",
            lti_iss="https://unknown.com",
        )
        assert result is None

    async def test_returns_learner_id_for_known(self, async_session):
        """Known sub+iss returns the learner_id."""
        created_id = await get_or_create_lti_learner(
            async_session,
            lti_sub="known-sub",
            lti_iss="https://known.com",
        )
        found_id = await get_learner_by_lti(
            async_session,
            lti_sub="known-sub",
            lti_iss="https://known.com",
        )
        assert found_id == created_id
