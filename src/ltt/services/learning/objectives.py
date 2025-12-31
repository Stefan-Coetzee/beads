"""
Learning objectives service.

Manages pedagogical goals attached to tasks using Bloom's taxonomy.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import (
    BloomLevel,
    LearningObjective,
    LearningObjectiveModel,
    ObjectiveTaxonomy,
    TaskModel,
)
from ltt.services.task_service import get_ancestors, get_children
from ltt.utils.ids import PREFIX_OBJECTIVE, generate_entity_id

# ============================================================================
# Exceptions
# ============================================================================


class LearningObjectiveError(Exception):
    """Base exception for learning objective operations."""


class LearningObjectiveNotFoundError(LearningObjectiveError):
    """Learning objective does not exist."""


class TaskNotFoundError(LearningObjectiveError):
    """Referenced task does not exist."""


# ============================================================================
# Learning Objective Operations
# ============================================================================


async def attach_objective(
    session: AsyncSession,
    task_id: str,
    description: str,
    level: BloomLevel,
    taxonomy: ObjectiveTaxonomy = ObjectiveTaxonomy.BLOOM,
) -> LearningObjective:
    """
    Attach a learning objective to a task.

    Args:
        session: Database session
        task_id: Task to attach to
        description: What the learner should achieve
        level: Bloom's taxonomy level
        taxonomy: Which taxonomy (default: bloom)

    Returns:
        Created learning objective

    Raises:
        TaskNotFoundError: If task doesn't exist
    """
    # Verify task exists
    task_result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = task_result.scalar_one_or_none()

    if not task:
        raise TaskNotFoundError(f"Task {task_id} does not exist")

    # Create objective
    objective_id = generate_entity_id(PREFIX_OBJECTIVE)
    objective = LearningObjectiveModel(
        id=objective_id,
        task_id=task_id,
        taxonomy=taxonomy.value,
        level=level.value if level else None,
        description=description,
    )
    session.add(objective)

    await session.commit()
    await session.refresh(objective)

    return LearningObjective.model_validate(objective)


async def get_objectives(
    session: AsyncSession,
    task_id: str,
) -> list[LearningObjective]:
    """
    Get all objectives for a task.

    Args:
        session: Database session
        task_id: Task ID

    Returns:
        List of learning objectives
    """
    result = await session.execute(
        select(LearningObjectiveModel).where(LearningObjectiveModel.task_id == task_id)
    )
    objectives = result.scalars().all()

    return [LearningObjective.model_validate(obj) for obj in objectives]


async def get_objectives_for_hierarchy(
    session: AsyncSession,
    task_id: str,
    include_ancestors: bool = True,
    include_descendants: bool = False,
) -> list[LearningObjective]:
    """
    Get objectives for a task and its hierarchy.

    Useful for loading full context:
    - Ancestor objectives: higher-level goals
    - Descendant objectives: breakdown of this task

    Args:
        session: Database session
        task_id: Task ID
        include_ancestors: Include objectives from parent tasks
        include_descendants: Include objectives from child tasks

    Returns:
        List of learning objectives from hierarchy
    """
    task_ids = [task_id]

    # Add ancestors
    if include_ancestors:
        ancestors = await get_ancestors(session, task_id)
        task_ids.extend([t.id for t in ancestors])

    # Add descendants
    if include_descendants:
        descendants = await get_children(session, task_id, recursive=True)
        task_ids.extend([t.id for t in descendants])

    # Get all objectives for these tasks
    result = await session.execute(
        select(LearningObjectiveModel).where(LearningObjectiveModel.task_id.in_(task_ids))
    )
    objectives = result.scalars().all()

    return [LearningObjective.model_validate(obj) for obj in objectives]


async def remove_objective(
    session: AsyncSession,
    objective_id: str,
) -> None:
    """
    Remove a learning objective.

    Args:
        session: Database session
        objective_id: Objective ID

    Raises:
        LearningObjectiveNotFoundError: If objective doesn't exist
    """
    result = await session.execute(
        select(LearningObjectiveModel).where(LearningObjectiveModel.id == objective_id)
    )
    objective = result.scalar_one_or_none()

    if not objective:
        raise LearningObjectiveNotFoundError(f"Learning objective {objective_id} does not exist")

    await session.delete(objective)
    await session.commit()
