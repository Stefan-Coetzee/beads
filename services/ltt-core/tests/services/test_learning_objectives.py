"""
Tests for learning objectives service.
"""

import pytest
from ltt.models import BloomLevel, ObjectiveTaxonomy, TaskCreate, TaskType
from ltt.services.learning import (
    LearningObjectiveNotFoundError,
    TaskNotFoundError,
    attach_objective,
    get_objectives,
    get_objectives_for_hierarchy,
    remove_objective,
)
from ltt.services.task_service import create_task


@pytest.mark.asyncio
async def test_attach_objective(async_session):
    """Test attaching a learning objective to a task."""
    # Create task
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    # Attach objective
    objective = await attach_objective(
        async_session,
        project.id,
        "Understand basic Python syntax",
        BloomLevel.UNDERSTAND,
    )

    assert objective.task_id == project.id
    assert objective.description == "Understand basic Python syntax"
    assert objective.level == BloomLevel.UNDERSTAND
    assert objective.taxonomy == ObjectiveTaxonomy.BLOOM


@pytest.mark.asyncio
async def test_attach_objective_to_nonexistent_task(async_session):
    """Test that attaching to non-existent task fails."""
    with pytest.raises(TaskNotFoundError, match="does not exist"):
        await attach_objective(
            async_session,
            "nonexistent-id",
            "Description",
            BloomLevel.REMEMBER,
        )


@pytest.mark.asyncio
async def test_get_objectives(async_session):
    """Test retrieving objectives for a task."""
    # Create task
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    # Attach multiple objectives
    await attach_objective(async_session, project.id, "Objective 1", BloomLevel.REMEMBER)
    await attach_objective(async_session, project.id, "Objective 2", BloomLevel.UNDERSTAND)
    await attach_objective(async_session, project.id, "Objective 3", BloomLevel.APPLY)

    # Get objectives
    objectives = await get_objectives(async_session, project.id)

    assert len(objectives) == 3
    descriptions = {obj.description for obj in objectives}
    assert descriptions == {"Objective 1", "Objective 2", "Objective 3"}


@pytest.mark.asyncio
async def test_get_objectives_for_hierarchy_includes_ancestors(async_session):
    """Test getting objectives from task and ancestors."""
    # Create hierarchy
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    epic = await create_task(
        async_session, TaskCreate(title="Epic", task_type=TaskType.EPIC, parent_id=project.id)
    )
    task = await create_task(
        async_session, TaskCreate(title="Task", task_type=TaskType.TASK, parent_id=epic.id)
    )

    # Attach objectives at different levels
    await attach_objective(async_session, project.id, "Project objective", BloomLevel.CREATE)
    await attach_objective(async_session, epic.id, "Epic objective", BloomLevel.ANALYZE)
    await attach_objective(async_session, task.id, "Task objective", BloomLevel.APPLY)

    # Get objectives for task (including ancestors)
    objectives = await get_objectives_for_hierarchy(async_session, task.id, include_ancestors=True)

    assert len(objectives) == 3
    descriptions = {obj.description for obj in objectives}
    assert descriptions == {"Project objective", "Epic objective", "Task objective"}


@pytest.mark.asyncio
async def test_get_objectives_for_hierarchy_includes_descendants(async_session):
    """Test getting objectives from task and descendants."""
    # Create hierarchy
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    epic = await create_task(
        async_session, TaskCreate(title="Epic", task_type=TaskType.EPIC, parent_id=project.id)
    )
    task = await create_task(
        async_session, TaskCreate(title="Task", task_type=TaskType.TASK, parent_id=epic.id)
    )

    # Attach objectives
    await attach_objective(async_session, project.id, "Project objective", BloomLevel.CREATE)
    await attach_objective(async_session, epic.id, "Epic objective", BloomLevel.ANALYZE)
    await attach_objective(async_session, task.id, "Task objective", BloomLevel.APPLY)

    # Get objectives for project (including descendants)
    objectives = await get_objectives_for_hierarchy(
        async_session, project.id, include_ancestors=False, include_descendants=True
    )

    assert len(objectives) == 3
    descriptions = {obj.description for obj in objectives}
    assert descriptions == {"Project objective", "Epic objective", "Task objective"}


@pytest.mark.asyncio
async def test_remove_objective(async_session):
    """Test removing a learning objective."""
    # Create task and objective
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    objective = await attach_objective(
        async_session, project.id, "To be removed", BloomLevel.REMEMBER
    )

    # Remove objective
    await remove_objective(async_session, objective.id)

    # Verify it's gone
    objectives = await get_objectives(async_session, project.id)
    assert len(objectives) == 0


@pytest.mark.asyncio
async def test_remove_nonexistent_objective(async_session):
    """Test that removing non-existent objective fails."""
    with pytest.raises(LearningObjectiveNotFoundError, match="does not exist"):
        await remove_objective(async_session, "nonexistent-id")
