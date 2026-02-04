"""
Submission service for the Learning Task Tracker.

Manages learner submissions and tracks attempt history.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import (
    Submission,
    SubmissionModel,
    SubmissionType,
    TaskModel,
    TaskStatus,
)
from ltt.utils.ids import PREFIX_SUBMISSION, generate_entity_id

# ============================================================================
# Exceptions
# ============================================================================


class SubmissionError(Exception):
    """Base exception for submission operations."""


class InvalidStateError(SubmissionError):
    """Task is in invalid state for submission."""


class SubmissionNotFoundError(SubmissionError):
    """Submission does not exist."""


class TaskNotFoundError(SubmissionError):
    """Referenced task does not exist."""


# ============================================================================
# Submission Operations
# ============================================================================


async def create_submission(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
    content: str,
    submission_type: SubmissionType,
) -> Submission:
    """
    Create a submission for a task.

    Automatically calculates attempt number based on previous submissions.

    Args:
        session: Database session
        task_id: Task being submitted for
        learner_id: Who is submitting
        content: The submission content
        submission_type: Type of content

    Returns:
        Created submission

    Raises:
        TaskNotFoundError: If task doesn't exist
        InvalidStateError: If task is closed
    """
    # 1. Verify task exists
    task_result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = task_result.scalar_one_or_none()

    if not task:
        raise TaskNotFoundError(f"Task {task_id} does not exist")

    # 2. Check learner's progress - task shouldn't be closed for this learner
    from ltt.services.progress_service import get_progress

    progress = await get_progress(session, task_id, learner_id)
    if progress and progress.status == TaskStatus.CLOSED:
        raise InvalidStateError(f"Task '{task_id}' is already closed for this learner")

    # 3. Calculate attempt number
    count_result = await session.execute(
        select(func.count())
        .select_from(SubmissionModel)
        .where(SubmissionModel.task_id == task_id)
        .where(SubmissionModel.learner_id == learner_id)
    )
    attempt_number = (count_result.scalar() or 0) + 1

    # 4. Create submission
    submission_id = generate_entity_id(PREFIX_SUBMISSION)
    submission = SubmissionModel(
        id=submission_id,
        task_id=task_id,
        learner_id=learner_id,
        submission_type=submission_type.value,
        content=content,
        attempt_number=attempt_number,
    )
    session.add(submission)

    await session.commit()
    await session.refresh(submission)

    return Submission.model_validate(submission)


async def get_submission(
    session: AsyncSession,
    submission_id: str,
) -> Submission:
    """
    Get a submission by ID.

    Args:
        session: Database session
        submission_id: Submission ID

    Returns:
        Submission

    Raises:
        SubmissionNotFoundError: If submission doesn't exist
    """
    result = await session.execute(
        select(SubmissionModel).where(SubmissionModel.id == submission_id)
    )
    submission = result.scalar_one_or_none()

    if not submission:
        raise SubmissionNotFoundError(f"Submission {submission_id} does not exist")

    return Submission.model_validate(submission)


async def get_submissions(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
    limit: int = 10,
) -> list[Submission]:
    """
    Get submissions for a task by a learner.

    Returns most recent first.

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID
        limit: Maximum number of submissions to return

    Returns:
        List of submissions (most recent first)
    """
    result = await session.execute(
        select(SubmissionModel)
        .where(SubmissionModel.task_id == task_id)
        .where(SubmissionModel.learner_id == learner_id)
        .order_by(SubmissionModel.attempt_number.desc())
        .limit(limit)
    )
    submissions = result.scalars().all()

    return [Submission.model_validate(sub) for sub in submissions]


async def get_latest_submission(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
) -> Submission | None:
    """
    Get the most recent submission for a task.

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID

    Returns:
        Latest submission or None if no submissions exist
    """
    result = await session.execute(
        select(SubmissionModel)
        .where(SubmissionModel.task_id == task_id)
        .where(SubmissionModel.learner_id == learner_id)
        .order_by(SubmissionModel.attempt_number.desc())
        .limit(1)
    )
    submission = result.scalar_one_or_none()

    return Submission.model_validate(submission) if submission else None


async def get_attempt_count(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
) -> int:
    """
    Get number of attempts for a task.

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID

    Returns:
        Number of attempts
    """
    result = await session.execute(
        select(func.count())
        .select_from(SubmissionModel)
        .where(SubmissionModel.task_id == task_id)
        .where(SubmissionModel.learner_id == learner_id)
    )
    return result.scalar() or 0
