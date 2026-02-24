"""
Test that epic-level blocking propagates to child tasks.

This test validates the fix for the issue where tasks under a blocked epic
were still showing as "ready" work even though their parent epic was blocked.
"""

import pytest
from ltt.models import DependencyType, LearnerModel, TaskCreate, TaskStatus, TaskType
from ltt.services.dependency_service import add_dependency, get_ready_work
from ltt.services.progress_service import close_task, update_status
from ltt.services.task_service import create_task
from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id


@pytest.mark.asyncio
async def test_epic_blocking_propagates_to_children(async_session):
    """Test that when Epic B is blocked by Epic A, tasks under Epic B are also blocked."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    # Create Epic A with a task (no subtasks to avoid validation requirements)
    epic_a = await create_task(
        async_session,
        TaskCreate(
            title="Epic A",
            task_type=TaskType.EPIC,
            parent_id=project.id,
            project_id=project.id,
        ),
    )
    task_a1 = await create_task(
        async_session,
        TaskCreate(
            title="Task A1",
            task_type=TaskType.TASK,
            parent_id=epic_a.id,
            project_id=project.id,
        ),
    )

    # Create Epic B with tasks (blocked by Epic A)
    epic_b = await create_task(
        async_session,
        TaskCreate(
            title="Epic B",
            task_type=TaskType.EPIC,
            parent_id=project.id,
            project_id=project.id,
        ),
    )
    task_b1 = await create_task(
        async_session,
        TaskCreate(
            title="Task B1",
            task_type=TaskType.TASK,
            parent_id=epic_b.id,
            project_id=project.id,
        ),
    )
    task_b2 = await create_task(
        async_session,
        TaskCreate(
            title="Task B2",
            task_type=TaskType.TASK,
            parent_id=epic_b.id,
            project_id=project.id,
        ),
    )

    # Add dependency: Epic B depends on Epic A
    await add_dependency(async_session, epic_b.id, epic_a.id, DependencyType.BLOCKS)

    # Get ready work - should only include Epic A and its children
    ready = await get_ready_work(async_session, project.id, learner_id)
    ready_ids = {t.id for t in ready}

    # Epic A and its children should be ready
    assert epic_a.id in ready_ids
    assert task_a1.id in ready_ids

    # Epic B and its children should NOT be ready (blocked by Epic A)
    assert epic_b.id not in ready_ids
    assert task_b1.id not in ready_ids
    assert task_b2.id not in ready_ids

    # Now complete Epic A (close it) - must close from bottom up
    await update_status(async_session, task_a1.id, learner_id, TaskStatus.IN_PROGRESS)
    await close_task(async_session, task_a1.id, learner_id, "Test completion")
    await update_status(async_session, epic_a.id, learner_id, TaskStatus.IN_PROGRESS)
    await close_task(async_session, epic_a.id, learner_id, "Test completion")

    # Get ready work again - now Epic B and its children should be unblocked
    ready_after = await get_ready_work(async_session, project.id, learner_id)
    ready_ids_after = {t.id for t in ready_after}

    # Epic B and its children should now be ready
    assert epic_b.id in ready_ids_after
    assert task_b1.id in ready_ids_after
    assert task_b2.id in ready_ids_after

    # Epic A should not appear (it's closed)
    assert epic_a.id not in ready_ids_after
    assert task_a1.id not in ready_ids_after


@pytest.mark.asyncio
async def test_nested_epic_blocking(async_session):
    """Test blocking propagation through multiple levels: Epic -> Task -> Subtask."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    # Create Epic 1 with nested structure
    epic_1 = await create_task(
        async_session,
        TaskCreate(
            title="Epic 1",
            task_type=TaskType.EPIC,
            parent_id=project.id,
            project_id=project.id,
        ),
    )

    # Create Epic 2 (blocked by Epic 1) with deeply nested structure
    epic_2 = await create_task(
        async_session,
        TaskCreate(
            title="Epic 2",
            task_type=TaskType.EPIC,
            parent_id=project.id,
            project_id=project.id,
        ),
    )
    task_2_1 = await create_task(
        async_session,
        TaskCreate(
            title="Task 2.1",
            task_type=TaskType.TASK,
            parent_id=epic_2.id,
            project_id=project.id,
        ),
    )
    subtask_2_1_1 = await create_task(
        async_session,
        TaskCreate(
            title="Subtask 2.1.1",
            task_type=TaskType.SUBTASK,
            parent_id=task_2_1.id,
            project_id=project.id,
        ),
    )
    task_2_2 = await create_task(
        async_session,
        TaskCreate(
            title="Task 2.2",
            task_type=TaskType.TASK,
            parent_id=epic_2.id,
            project_id=project.id,
        ),
    )

    # Block Epic 2 by Epic 1
    await add_dependency(async_session, epic_2.id, epic_1.id, DependencyType.BLOCKS)

    # Get ready work
    ready = await get_ready_work(async_session, project.id, learner_id)
    ready_ids = {t.id for t in ready}

    # Only Epic 1 should be ready
    assert epic_1.id in ready_ids

    # Epic 2 and ALL its descendants should be blocked
    assert epic_2.id not in ready_ids
    assert task_2_1.id not in ready_ids
    assert subtask_2_1_1.id not in ready_ids
    assert task_2_2.id not in ready_ids


@pytest.mark.asyncio
async def test_task_level_blocking_independent_of_epic_blocking(async_session):
    """Test that task-level dependencies work independently of epic blocking."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )

    # Create Epic A with two tasks
    epic_a = await create_task(
        async_session,
        TaskCreate(
            title="Epic A",
            task_type=TaskType.EPIC,
            parent_id=project.id,
            project_id=project.id,
        ),
    )
    task_a1 = await create_task(
        async_session,
        TaskCreate(
            title="Task A1",
            task_type=TaskType.TASK,
            parent_id=epic_a.id,
            project_id=project.id,
        ),
    )
    task_a2 = await create_task(
        async_session,
        TaskCreate(
            title="Task A2",
            task_type=TaskType.TASK,
            parent_id=epic_a.id,
            project_id=project.id,
        ),
    )

    # Task A2 depends on Task A1 (within same epic)
    await add_dependency(async_session, task_a2.id, task_a1.id, DependencyType.BLOCKS)

    # Get ready work
    ready = await get_ready_work(async_session, project.id, learner_id)
    ready_ids = {t.id for t in ready}

    # Epic A and Task A1 should be ready
    assert epic_a.id in ready_ids
    assert task_a1.id in ready_ids

    # Task A2 should be blocked (by Task A1)
    assert task_a2.id not in ready_ids

    # Complete Task A1
    await update_status(async_session, task_a1.id, learner_id, TaskStatus.IN_PROGRESS)
    await close_task(async_session, task_a1.id, learner_id, "Test completion")

    # Get ready work again
    ready_after = await get_ready_work(async_session, project.id, learner_id)
    ready_ids_after = {t.id for t in ready_after}

    # Now Task A2 should be unblocked
    assert task_a2.id in ready_ids_after
