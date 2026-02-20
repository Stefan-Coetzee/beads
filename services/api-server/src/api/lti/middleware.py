"""
LTI session resolution.

Resolves launch_id to LTI context for API requests after the initial launch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .adapter import FastAPIMessageLaunch, FastAPIRequest
from .config import get_tool_config
from .storage import RedisLaunchDataStorage


@dataclass
class LTIContext:
    """LTI context resolved from a launch_id."""

    launch_id: str
    learner_sub: str
    learner_id: str  # Resolved from mapping table
    project_id: Optional[str]
    has_ags: bool
    is_instructor: bool


def resolve_launch(
    launch_id: str, storage: RedisLaunchDataStorage
) -> Optional[LTIContext]:
    """
    Resolve a launch_id to LTI context.

    Returns None if launch_id is not found (expired or invalid).
    """
    tool_conf = get_tool_config()

    dummy_request = FastAPIRequest(
        cookies={}, session={}, request_data={}, request_is_secure=True
    )

    try:
        message_launch = FastAPIMessageLaunch.from_cache(
            launch_id,
            dummy_request,
            tool_conf,
            launch_data_storage=storage,
        )
    except Exception:
        return None

    launch_data = message_launch.get_launch_data()
    custom = launch_data.get(
        "https://purl.imsglobal.org/spec/lti/claim/custom", {}
    )

    return LTIContext(
        launch_id=launch_id,
        learner_sub=launch_data.get("sub", ""),
        learner_id="",  # Caller resolves from mapping table
        project_id=custom.get("project_id"),
        has_ags=message_launch.has_ags(),
        is_instructor=message_launch.check_teacher_access(),
    )
