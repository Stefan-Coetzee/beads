"""
AGS grade passback service.

Sends learner progress scores to the LMS via LTI AGS.
Grade passback failures never block the learner experience.
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional

from pylti1p3.grade import Grade
from pylti1p3.lineitem import LineItem

from .adapter import FastAPIMessageLaunch, FastAPIRequest
from .config import get_tool_config
from .storage import RedisLaunchDataStorage

logger = logging.getLogger(__name__)


def send_grade(
    launch_id: str,
    storage: RedisLaunchDataStorage,
    learner_sub: str,
    score: float,
    max_score: float,
    activity_progress: str = "Completed",
    grading_progress: str = "FullyGraded",
    comment: Optional[str] = None,
) -> bool:
    """
    Send a grade to the LMS via AGS.

    Returns True if grade was sent successfully, False otherwise.
    """
    tool_conf = get_tool_config()

    # Reconstruct message launch from cache
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
    except Exception as e:
        logger.warning("Failed to restore LTI launch %s: %s", launch_id, e)
        return False

    if not message_launch.has_ags():
        logger.info("AGS not available for launch %s", launch_id)
        return False

    ags = message_launch.get_ags()

    # Get resource_link_id from cached launch data
    launch_data = message_launch.get_launch_data()
    resource_link = launch_data.get(
        "https://purl.imsglobal.org/spec/lti/claim/resource_link", {}
    )

    # Build grade
    grade = Grade()
    grade.set_score_given(score)
    grade.set_score_maximum(max_score)
    grade.set_timestamp(datetime.datetime.utcnow().isoformat() + "Z")
    grade.set_activity_progress(activity_progress)
    grade.set_grading_progress(grading_progress)
    grade.set_user_id(learner_sub)

    if comment:
        grade.set_comment(comment)

    # Build line item (describes the gradebook column)
    line_item = LineItem()
    line_item.set_tag("ltt-progress")
    line_item.set_score_maximum(max_score)
    line_item.set_label("Project Progress")
    if resource_link.get("id"):
        line_item.set_resource_id(resource_link["id"])

    try:
        ags.put_grade(grade, line_item)
        logger.info(
            "Grade sent: %s/%s for sub=%s launch=%s",
            score, max_score, learner_sub, launch_id,
        )
        return True
    except Exception as e:
        logger.error("AGS grade passback failed: %s", e)
        return False


def maybe_send_grade(
    learner_id: str,
    project_id: str,
    completed: int,
    total: int,
    storage: Optional[RedisLaunchDataStorage] = None,
) -> bool:
    """
    Send grade if this learner has an active LTI session.

    No-op for standalone (non-LTI) sessions.
    """
    if storage is None:
        return False

    # Look up active launch mapping from Redis
    key = f"active:{learner_id}:{project_id}"
    result = storage.get_value(key)
    if not result or not isinstance(result, dict):
        return False

    launch_id = result.get("launch_id")
    learner_sub = result.get("sub")
    if not launch_id or not learner_sub:
        return False

    return send_grade(
        launch_id=launch_id,
        storage=storage,
        learner_sub=learner_sub,
        score=float(completed),
        max_score=float(total),
        activity_progress="Completed" if completed == total else "InProgress",
        grading_progress="FullyGraded" if completed == total else "Pending",
        comment=f"Completed {completed}/{total} tasks ({completed / total * 100:.0f}%)" if total > 0 else None,
    )
