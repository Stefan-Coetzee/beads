"""
Progress and Status Management Service for the Learning Task Tracker.

Handles learner-specific task progress and status transitions.
Works with the INSTANCE LAYER (learner_task_progress table).
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import (
    LearnerTaskProgress,
    LearnerTaskProgressModel,
    TaskModel,
    TaskStatus,
)
from ltt.utils.ids import PREFIX_LEARNER_TASK_PROGRESS, generate_entity_id

# Valid status transitions
VALID_TRANSITIONS = {
    TaskStatus.OPEN: [TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED],
    TaskStatus.IN_PROGRESS: [
        TaskStatus.OPEN,
        TaskStatus.BLOCKED,
        TaskStatus.CLOSED,
    ],
    TaskStatus.BLOCKED: [TaskStatus.OPEN, TaskStatus.IN_PROGRESS],
    TaskStatus.CLOSED: [TaskStatus.OPEN],  # Only via explicit "go_back"
}


class InvalidStatusTransitionError(Exception):
    """Raised when a status transition is invalid."""

    pass


class TaskNotFoundError(Exception):
    """Raised when a task cannot be found."""

    pass


async def get_or_create_progress(
    session: AsyncSession, task_id: str, learner_id: str
) -> LearnerTaskProgressModel:
    """
    Get or create progress record for a learner on a task.

    Implements lazy initialization: if no record exists, create one with status='open'.

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID

    Returns:
        Progress record
    """
    # Try to get existing progress
    result = await session.execute(
        select(LearnerTaskProgressModel).where(
            LearnerTaskProgressModel.task_id == task_id,
            LearnerTaskProgressModel.learner_id == learner_id,
        )
    )
    progress = result.scalar_one_or_none()

    if progress:
        return progress

    # Create new progress record with default status='open'
    progress = LearnerTaskProgressModel(
        id=generate_entity_id(PREFIX_LEARNER_TASK_PROGRESS),
        task_id=task_id,
        learner_id=learner_id,
        status=TaskStatus.OPEN.value,
    )

    session.add(progress)
    await session.flush()  # Flush but don't commit yet

    return progress


async def get_progress(
    session: AsyncSession, task_id: str, learner_id: str
) -> LearnerTaskProgress | None:
    """
    Get progress record for a learner on a task.

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID

    Returns:
        Progress record or None if it doesn't exist
    """
    result = await session.execute(
        select(LearnerTaskProgressModel).where(
            LearnerTaskProgressModel.task_id == task_id,
            LearnerTaskProgressModel.learner_id == learner_id,
        )
    )
    progress = result.scalar_one_or_none()

    if not progress:
        return None

    return LearnerTaskProgress.model_validate(progress)


async def update_status(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
    new_status: TaskStatus,
    close_reason: str | None = None,
) -> LearnerTaskProgress:
    """
    Update the status of a task for a specific learner.

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID
        new_status: New status
        close_reason: Reason for closing (required if new_status is CLOSED)

    Returns:
        Updated progress record

    Raises:
        TaskNotFoundError: If task does not exist
        InvalidStatusTransitionError: If transition is not allowed
    """
    # Verify task exists
    task = await session.get(TaskModel, task_id)
    if not task:
        raise TaskNotFoundError(f"Task {task_id} not found")

    # Get or create progress record
    progress = await get_or_create_progress(session, task_id, learner_id)
    current_status = TaskStatus(progress.status)

    # Validate transition
    if new_status not in VALID_TRANSITIONS.get(current_status, []):
        raise InvalidStatusTransitionError(
            f"Cannot transition from {current_status.value} to {new_status.value}"
        )

    # Additional validation for closing
    if new_status == TaskStatus.CLOSED:
        # Check that all children are closed FOR THIS LEARNER
        result = await session.execute(select(TaskModel).where(TaskModel.parent_id == task_id))
        children = result.scalars().all()

        for child in children:
            child_progress = await get_or_create_progress(session, child.id, learner_id)
            if child_progress.status != TaskStatus.CLOSED.value:
                raise InvalidStatusTransitionError(
                    f"Cannot close task: child {child.id} is still {child_progress.status}"
                )

    # Update status
    progress.status = new_status.value

    # Update timestamps based on status
    if new_status == TaskStatus.IN_PROGRESS and not progress.started_at:
        progress.started_at = datetime.utcnow()
    elif new_status == TaskStatus.CLOSED:
        progress.completed_at = datetime.utcnow()
        progress.close_reason = close_reason
    elif new_status == TaskStatus.OPEN:
        # Reopening - clear completion timestamp
        progress.completed_at = None
        progress.close_reason = None

    progress.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(progress)

    return LearnerTaskProgress.model_validate(progress)


async def start_task(session: AsyncSession, task_id: str, learner_id: str) -> LearnerTaskProgress:
    """
    Start working on a task (transition to IN_PROGRESS).

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID

    Returns:
        Updated progress record
    """
    return await update_status(session, task_id, learner_id, TaskStatus.IN_PROGRESS)


async def close_task(
    session: AsyncSession, task_id: str, learner_id: str, reason: str
) -> LearnerTaskProgress:
    """
    Close a task (transition to CLOSED).

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID
        reason: Reason for closing

    Returns:
        Updated progress record
    """
    return await update_status(session, task_id, learner_id, TaskStatus.CLOSED, close_reason=reason)


async def reopen_task(session: AsyncSession, task_id: str, learner_id: str) -> LearnerTaskProgress:
    """
    Reopen a closed task (transition back to OPEN).

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID

    Returns:
        Updated progress record
    """
    return await update_status(session, task_id, learner_id, TaskStatus.OPEN)


async def get_learner_tasks_by_status(
    session: AsyncSession, learner_id: str, status: TaskStatus, project_id: str | None = None
) -> list[tuple[TaskModel, LearnerTaskProgressModel]]:
    """
    Get all tasks for a learner with a specific status.

    Args:
        session: Database session
        learner_id: Learner ID
        status: Status to filter by
        project_id: Optional project ID filter

    Returns:
        List of (task, progress) tuples
    """
    # Build query joining tasks with learner_task_progress
    query = (
        select(TaskModel, LearnerTaskProgressModel)
        .join(
            LearnerTaskProgressModel,
            (TaskModel.id == LearnerTaskProgressModel.task_id)
            & (LearnerTaskProgressModel.learner_id == learner_id),
        )
        .where(LearnerTaskProgressModel.status == status.value)
    )

    if project_id:
        query = query.where(TaskModel.project_id == project_id)

    result = await session.execute(query)
    return result.all()
