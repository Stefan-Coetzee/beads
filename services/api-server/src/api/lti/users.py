"""
LTI user identity mapping.

Maps LTI sub+iss to internal LTT learner IDs.
Creates new learner records on first LTI launch.
"""

from __future__ import annotations

import json

from ltt.models.learner import LearnerModel
from ltt.models.lti_mapping import LTIUserMapping
from ltt.utils.ids import generate_entity_id
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_or_create_lti_learner(
    session: AsyncSession,
    lti_sub: str,
    lti_iss: str,
    name: str | None = None,
    email: str | None = None,
) -> str:
    """
    Map an LTI user to an LTT learner_id.

    If the user has launched before, returns the existing learner_id.
    If this is their first launch, creates a new learner and mapping.

    Returns:
        The LTT learner_id (e.g., "learner-a1b2c3d4")
    """
    # Check for existing mapping
    result = await session.execute(
        select(LTIUserMapping).where(
            LTIUserMapping.lti_sub == lti_sub,
            LTIUserMapping.lti_iss == lti_iss,
        )
    )
    mapping = result.scalar_one_or_none()

    if mapping:
        # Update cached PII if changed
        changed = False
        if name and mapping.name != name:
            mapping.name = name
            changed = True
        if email and mapping.email != email:
            mapping.email = email
            changed = True
        if changed:
            await session.commit()
        return mapping.learner_id

    # First launch: create learner + mapping
    learner_id = generate_entity_id("learner")

    metadata = json.dumps(
        {
            "name": name or "",
            "email": email or "",
            "lti_sub": lti_sub,
            "lti_iss": lti_iss,
            "source": "lti",
        }
    )

    learner = LearnerModel(id=learner_id, learner_metadata=metadata)
    session.add(learner)

    mapping = LTIUserMapping(
        id=generate_entity_id("lti"),
        lti_sub=lti_sub,
        lti_iss=lti_iss,
        learner_id=learner_id,
        name=name,
        email=email,
    )
    session.add(mapping)

    await session.commit()
    return learner_id


async def get_learner_by_lti(
    session: AsyncSession,
    lti_sub: str,
    lti_iss: str,
) -> str | None:
    """Look up learner_id by LTI identity. Returns None if not found."""
    result = await session.execute(
        select(LTIUserMapping.learner_id).where(
            LTIUserMapping.lti_sub == lti_sub,
            LTIUserMapping.lti_iss == lti_iss,
        )
    )
    return result.scalar_one_or_none()
