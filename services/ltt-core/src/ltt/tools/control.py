"""
Control tools for agent interface.

Tools for special actions: go_back, request_help.

Implementation Note (ADR-001):
- Reopening updates learner_task_progress.status, not task.status
- Only affects this learner's progress record
- Other learners' progress is unchanged
"""

from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import CommentCreate, TaskStatus
from ltt.services.progress_service import get_or_create_progress, reopen_task
from ltt.services.task_service import add_comment
from ltt.tools.schemas import GoBackInput, GoBackOutput, RequestHelpInput, RequestHelpOutput


async def go_back(input: GoBackInput, learner_id: str, session: AsyncSession) -> GoBackOutput:
    """
    Reopen a closed task.

    Use when learner wants to redo or the task was closed prematurely.
    Requires a reason for the audit trail.

    Implementation Note (ADR-001):
    - Reopening updates learner_task_progress.status, not task.status
    - Only affects this learner's progress record
    - Other learners' progress is unchanged
    """
    # Get learner's progress record
    progress = await get_or_create_progress(session, input.task_id, learner_id)

    if progress.status != TaskStatus.CLOSED.value:
        return GoBackOutput(
            success=False,
            task_id=input.task_id,
            new_status=progress.status,
            message=f"Task is not closed (status: {progress.status})",
            reason=input.reason,
        )

    # Reopen the task for this learner
    reopened = await reopen_task(session, input.task_id, learner_id)

    return GoBackOutput(
        success=True,
        task_id=input.task_id,
        new_status=reopened.status,
        message=f"Task reopened: {input.reason}",
        reason=input.reason,
    )


async def request_help(
    input: RequestHelpInput, learner_id: str, session: AsyncSession
) -> RequestHelpOutput:
    """
    Request human help for a task.

    Creates a help request that can be reviewed by instructors.
    """
    # Create a comment tagged as help request
    comment_data = CommentCreate(
        task_id=input.task_id,
        learner_id=learner_id,
        author=learner_id,
        text=f"[HELP REQUEST] {input.message}",
    )

    comment = await add_comment(session, input.task_id, comment_data)

    # Future: could create a separate help_requests table
    # and notify instructors

    return RequestHelpOutput(
        request_id=comment.id, message="Help request submitted. An instructor will review it."
    )
