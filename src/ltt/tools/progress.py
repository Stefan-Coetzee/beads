"""
Progress tools for agent interface.

Tools for tracking progress: start_task, submit.

Implementation Note (ADR-001):
- Status updates go to learner_task_progress table
- Lazy initialization: creates progress record if doesn't exist
- Validation and submission are learner-scoped
"""

from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import SubmissionType, TaskStatus
from ltt.services.dependency_service import is_task_blocked
from ltt.services.progress_service import get_or_create_progress, update_status
from ltt.services.submission_service import create_submission
from ltt.services.task_service import get_task
from ltt.services.validation_service import can_close_task, validate_submission
from ltt.tools.navigation import get_context
from ltt.tools.schemas import (
    GetContextInput,
    StartTaskInput,
    StartTaskOutput,
    SubmitInput,
    SubmitOutput,
)


async def start_task(
    input: StartTaskInput, learner_id: str, session: AsyncSession
) -> StartTaskOutput:
    """
    Start working on a task.

    Sets status to in_progress and returns full context for the task.
    This is the primary way to begin work on a task.

    Implementation Note (ADR-001):
    - Status is written to learner_task_progress, not tasks table
    - Creates progress record if it doesn't exist (lazy initialization)
    - Checks blocking against learner's own progress
    """
    # Get task details
    task = await get_task(session, input.task_id)

    # Get or create learner's progress record
    progress = await get_or_create_progress(session, input.task_id, learner_id)
    old_status = progress.status

    # Check if task can be started
    if progress.status == TaskStatus.CLOSED.value:
        return StartTaskOutput(
            success=False,
            task_id=input.task_id,
            old_status=old_status,
            new_status=old_status,
            message="Cannot start a closed task. Use go_back to reopen it first.",
            context=None,
            newly_unblocked=[],
        )

    # Check if task is blocked by dependencies (regardless of status)
    is_blocked, blockers = await is_task_blocked(session, input.task_id, learner_id)
    if is_blocked:
        blocker_titles = [b.title for b in blockers[:3]]
        return StartTaskOutput(
            success=False,
            task_id=input.task_id,
            old_status=old_status,
            new_status=old_status,
            message=f"Task is blocked by {len(blockers)} other task(s): {', '.join(blocker_titles)}",
            context=None,
            newly_unblocked=[],
        )

    # Set to in_progress if not already
    if progress.status != TaskStatus.IN_PROGRESS.value:
        await update_status(session, input.task_id, learner_id, TaskStatus.IN_PROGRESS)

    # Load full context
    context_output = await get_context(GetContextInput(task_id=input.task_id), learner_id, session)

    return StartTaskOutput(
        success=True,
        task_id=input.task_id,
        old_status=old_status,
        new_status=TaskStatus.IN_PROGRESS.value,
        message=f"Started working on '{task.title}'",
        context=context_output,
        newly_unblocked=[],
    )


async def submit(input: SubmitInput, learner_id: str, session: AsyncSession) -> SubmitOutput:
    """
    Submit work for a task and trigger validation.

    Returns validation result and whether task can be closed.
    """
    # Parse submission type (enum values are lowercase)
    try:
        sub_type = SubmissionType(input.submission_type.lower())
    except ValueError:
        return SubmitOutput(
            success=False,
            submission_id="",
            attempt_number=0,
            validation_passed=None,
            validation_message=f"Invalid submission type: {input.submission_type}",
            can_close_task=False,
            message=f"Invalid submission type: {input.submission_type}",
        )

    # Create submission
    submission = await create_submission(
        session, input.task_id, learner_id, input.content, sub_type
    )

    # Validate submission
    validation = await validate_submission(session, submission.id)

    # Check if task can be closed
    can_close, close_message = await can_close_task(session, input.task_id, learner_id)

    if validation.passed:
        message = f"Submission passed validation! (Attempt #{submission.attempt_number})"
    else:
        message = f"Submission failed: {validation.error_message}"

    return SubmitOutput(
        success=True,
        submission_id=submission.id,
        attempt_number=submission.attempt_number,
        validation_passed=validation.passed,
        validation_message=validation.error_message if not validation.passed else None,
        can_close_task=can_close,
        message=message,
    )
