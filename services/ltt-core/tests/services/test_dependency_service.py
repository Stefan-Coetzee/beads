"""
Tests for dependency management service.
"""

import pytest
from sqlalchemy import select

from ltt.models import (
    DependencyModel,
    DependencyType,
    LearnerModel,
    TaskCreate,
    TaskType,
)
from ltt.services.dependency_service import (
    CycleError,
    DependencyNotFoundError,
    DuplicateError,
    TaskNotFoundError,
    add_dependency,
    detect_cycles,
    get_blocked_tasks,
    get_blocking_tasks,
    get_dependencies,
    get_dependents,
    get_ready_work,
    is_task_blocked,
    is_task_ready,
    remove_dependency,
    would_create_cycle,
)
from ltt.services.progress_service import update_status
from ltt.services.task_service import create_task
from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id


@pytest.mark.asyncio
async def test_add_dependency(async_session):
    """Test adding a dependency between tasks."""
    # Create two tasks
    task1 = await create_task(async_session, TaskCreate(title="Task 1", task_type=TaskType.PROJECT))
    task2 = await create_task(
        async_session, TaskCreate(title="Task 2", task_type=TaskType.EPIC, parent_id=task1.id)
    )

    # Add dependency: Task 2 depends on Task 1
    dep = await add_dependency(async_session, task2.id, task1.id)

    assert dep.task_id == task2.id
    assert dep.depends_on_id == task1.id
    assert dep.dependency_type == DependencyType.BLOCKS
    assert dep.created_by == "system"


@pytest.mark.asyncio
async def test_add_dependency_nonexistent_task(async_session):
    """Test that adding dependency with non-existent task fails."""
    task1 = await create_task(async_session, TaskCreate(title="Task 1", task_type=TaskType.PROJECT))

    with pytest.raises(TaskNotFoundError, match="does not exist"):
        await add_dependency(async_session, task1.id, "nonexistent-id")


@pytest.mark.asyncio
async def test_add_duplicate_dependency(async_session):
    """Test that adding duplicate dependency fails."""
    task1 = await create_task(async_session, TaskCreate(title="Task 1", task_type=TaskType.PROJECT))
    task2 = await create_task(
        async_session, TaskCreate(title="Task 2", task_type=TaskType.EPIC, parent_id=task1.id)
    )

    # Add dependency once
    await add_dependency(async_session, task2.id, task1.id)

    # Try to add same dependency again
    with pytest.raises(DuplicateError, match="already exists"):
        await add_dependency(async_session, task2.id, task1.id)


@pytest.mark.asyncio
async def test_remove_dependency(async_session):
    """Test removing a dependency."""
    task1 = await create_task(async_session, TaskCreate(title="Task 1", task_type=TaskType.PROJECT))
    task2 = await create_task(
        async_session, TaskCreate(title="Task 2", task_type=TaskType.EPIC, parent_id=task1.id)
    )

    # Add and then remove dependency
    await add_dependency(async_session, task2.id, task1.id)
    await remove_dependency(async_session, task2.id, task1.id)

    # Verify dependency is removed
    result = await async_session.execute(
        select(DependencyModel)
        .where(DependencyModel.task_id == task2.id)
        .where(DependencyModel.depends_on_id == task1.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_remove_nonexistent_dependency(async_session):
    """Test that removing non-existent dependency fails."""
    task1 = await create_task(async_session, TaskCreate(title="Task 1", task_type=TaskType.PROJECT))
    task2 = await create_task(
        async_session, TaskCreate(title="Task 2", task_type=TaskType.EPIC, parent_id=task1.id)
    )

    with pytest.raises(DependencyNotFoundError, match="does not exist"):
        await remove_dependency(async_session, task2.id, task1.id)


@pytest.mark.asyncio
async def test_get_dependencies(async_session):
    """Test retrieving dependencies for a task."""
    task1 = await create_task(async_session, TaskCreate(title="Task 1", task_type=TaskType.PROJECT))
    task2 = await create_task(
        async_session, TaskCreate(title="Task 2", task_type=TaskType.EPIC, parent_id=task1.id)
    )
    task3 = await create_task(
        async_session, TaskCreate(title="Task 3", task_type=TaskType.EPIC, parent_id=task1.id)
    )

    # Task 2 depends on both Task 1 and Task 3
    await add_dependency(async_session, task2.id, task1.id)
    await add_dependency(async_session, task2.id, task3.id, DependencyType.RELATED)

    # Get all dependencies
    deps = await get_dependencies(async_session, task2.id)
    assert len(deps) == 2

    # Get only blocking dependencies
    blocking_deps = await get_dependencies(async_session, task2.id, DependencyType.BLOCKS)
    assert len(blocking_deps) == 1
    assert blocking_deps[0].depends_on_id == task1.id


@pytest.mark.asyncio
async def test_get_dependents(async_session):
    """Test retrieving dependents of a task."""
    task1 = await create_task(async_session, TaskCreate(title="Task 1", task_type=TaskType.PROJECT))
    task2 = await create_task(
        async_session, TaskCreate(title="Task 2", task_type=TaskType.EPIC, parent_id=task1.id)
    )
    task3 = await create_task(
        async_session, TaskCreate(title="Task 3", task_type=TaskType.EPIC, parent_id=task1.id)
    )

    # Both Task 2 and Task 3 depend on Task 1
    await add_dependency(async_session, task2.id, task1.id)
    await add_dependency(async_session, task3.id, task1.id)

    # Get dependents of Task 1
    dependents = await get_dependents(async_session, task1.id)
    assert len(dependents) == 2

    dependent_ids = {dep.task_id for dep in dependents}
    assert dependent_ids == {task2.id, task3.id}


@pytest.mark.asyncio
async def test_cycle_detection_self_loop(async_session):
    """Test that self-loops are detected."""
    task1 = await create_task(async_session, TaskCreate(title="Task 1", task_type=TaskType.PROJECT))

    with pytest.raises(CycleError, match="would create a cycle"):
        await add_dependency(async_session, task1.id, task1.id)


@pytest.mark.asyncio
async def test_cycle_detection_two_nodes(async_session):
    """Test detecting A -> B -> A cycle."""
    task1 = await create_task(async_session, TaskCreate(title="Task 1", task_type=TaskType.PROJECT))
    task2 = await create_task(
        async_session, TaskCreate(title="Task 2", task_type=TaskType.EPIC, parent_id=task1.id)
    )

    # Create A -> B
    await add_dependency(async_session, task1.id, task2.id)

    # Try to create B -> A (would close the cycle)
    with pytest.raises(CycleError, match="would create a cycle"):
        await add_dependency(async_session, task2.id, task1.id)


@pytest.mark.asyncio
async def test_cycle_detection_three_nodes(async_session):
    """Test detecting A -> B -> C -> A cycle."""
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task_a = await create_task(
        async_session, TaskCreate(title="Task A", task_type=TaskType.TASK, parent_id=project.id)
    )
    task_b = await create_task(
        async_session, TaskCreate(title="Task B", task_type=TaskType.TASK, parent_id=project.id)
    )
    task_c = await create_task(
        async_session, TaskCreate(title="Task C", task_type=TaskType.TASK, parent_id=project.id)
    )

    # Create A -> B -> C
    await add_dependency(async_session, task_a.id, task_b.id)
    await add_dependency(async_session, task_b.id, task_c.id)

    # Try to create C -> A (would close the cycle)
    with pytest.raises(CycleError, match="would create a cycle"):
        await add_dependency(async_session, task_c.id, task_a.id)


@pytest.mark.asyncio
async def test_would_create_cycle_helper(async_session):
    """Test the would_create_cycle helper function."""
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task_a = await create_task(
        async_session, TaskCreate(title="Task A", task_type=TaskType.TASK, parent_id=project.id)
    )
    task_b = await create_task(
        async_session, TaskCreate(title="Task B", task_type=TaskType.TASK, parent_id=project.id)
    )
    task_c = await create_task(
        async_session, TaskCreate(title="Task C", task_type=TaskType.TASK, parent_id=project.id)
    )

    # Create A -> B
    await add_dependency(async_session, task_a.id, task_b.id)

    # Check B -> A would cycle
    assert await would_create_cycle(async_session, task_b.id, task_a.id) is True

    # Check B -> C would not cycle
    assert await would_create_cycle(async_session, task_b.id, task_c.id) is False


@pytest.mark.asyncio
async def test_detect_cycles_finds_all_cycles(async_session):
    """Test detecting all cycles in a dependency graph."""
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task_a = await create_task(
        async_session, TaskCreate(title="Task A", task_type=TaskType.TASK, parent_id=project.id)
    )
    task_b = await create_task(
        async_session, TaskCreate(title="Task B", task_type=TaskType.TASK, parent_id=project.id)
    )
    task_c = await create_task(
        async_session, TaskCreate(title="Task C", task_type=TaskType.TASK, parent_id=project.id)
    )

    # Create cycle A -> B -> C -> A (bypassing validation for test)
    dep1 = DependencyModel(task_id=task_a.id, depends_on_id=task_b.id, dependency_type="blocks")
    dep2 = DependencyModel(task_id=task_b.id, depends_on_id=task_c.id, dependency_type="blocks")
    dep3 = DependencyModel(task_id=task_c.id, depends_on_id=task_a.id, dependency_type="blocks")
    async_session.add_all([dep1, dep2, dep3])
    await async_session.commit()

    # Detect cycles
    cycles = await detect_cycles(async_session, project.id)

    assert len(cycles) == 1
    cycle = cycles[0]
    assert len(cycle) == 3
    assert set(cycle) == {task_a.id, task_b.id, task_c.id}


@pytest.mark.asyncio
async def test_get_blocking_tasks_per_learner(async_session):
    """Test getting blocking tasks for a specific learner."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create tasks
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task1 = await create_task(
        async_session, TaskCreate(title="Task 1", task_type=TaskType.TASK, parent_id=project.id)
    )
    task2 = await create_task(
        async_session, TaskCreate(title="Task 2", task_type=TaskType.TASK, parent_id=project.id)
    )

    # Task 2 depends on Task 1
    await add_dependency(async_session, task2.id, task1.id)

    # For learner, Task 1 is blocking Task 2 (default status is 'open')
    blockers = await get_blocking_tasks(async_session, task2.id, learner_id)
    assert len(blockers) == 1
    assert blockers[0].id == task1.id

    # Close Task 1 for learner (OPEN -> IN_PROGRESS -> CLOSED)
    from ltt.models import TaskStatus

    await update_status(async_session, task1.id, learner_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task1.id, learner_id, TaskStatus.CLOSED)

    # Now Task 1 should not block Task 2 for this learner
    blockers_after = await get_blocking_tasks(async_session, task2.id, learner_id)
    assert len(blockers_after) == 0


@pytest.mark.asyncio
async def test_is_task_blocked_per_learner(async_session):
    """Test checking if task is blocked for a learner."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create tasks
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task1 = await create_task(
        async_session, TaskCreate(title="Task 1", task_type=TaskType.TASK, parent_id=project.id)
    )
    task2 = await create_task(
        async_session, TaskCreate(title="Task 2", task_type=TaskType.TASK, parent_id=project.id)
    )

    # Task 2 depends on Task 1
    await add_dependency(async_session, task2.id, task1.id)

    # Check if Task 2 is blocked
    is_blocked, blockers = await is_task_blocked(async_session, task2.id, learner_id)
    assert is_blocked is True
    assert len(blockers) == 1


@pytest.mark.asyncio
async def test_is_task_ready_per_learner(async_session):
    """Test checking if task is ready for a learner."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create tasks
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task1 = await create_task(
        async_session, TaskCreate(title="Task 1", task_type=TaskType.TASK, parent_id=project.id)
    )
    task2 = await create_task(
        async_session, TaskCreate(title="Task 2", task_type=TaskType.TASK, parent_id=project.id)
    )

    # Task 2 depends on Task 1
    await add_dependency(async_session, task2.id, task1.id)

    # Task 1 is ready (no blockers)
    assert await is_task_ready(async_session, task1.id, learner_id) is True

    # Task 2 is not ready (blocked by Task 1)
    assert await is_task_ready(async_session, task2.id, learner_id) is False

    # Close Task 1 for learner (OPEN -> IN_PROGRESS -> CLOSED)
    from ltt.models import TaskStatus

    await update_status(async_session, task1.id, learner_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task1.id, learner_id, TaskStatus.CLOSED)

    # Now Task 2 is ready
    assert await is_task_ready(async_session, task2.id, learner_id) is True


@pytest.mark.asyncio
async def test_get_ready_work_excludes_blocked_per_learner(async_session):
    """Test that ready work excludes blocked tasks for a learner."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create tasks
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task1 = await create_task(
        async_session, TaskCreate(title="Task 1", task_type=TaskType.TASK, parent_id=project.id)
    )
    task2 = await create_task(
        async_session, TaskCreate(title="Task 2", task_type=TaskType.TASK, parent_id=project.id)
    )
    task3 = await create_task(
        async_session, TaskCreate(title="Task 3", task_type=TaskType.TASK, parent_id=project.id)
    )

    # Task 2 depends on Task 1, Task 3 is independent
    await add_dependency(async_session, task2.id, task1.id)

    # Get ready work - should include Task 1 and Task 3, but not Task 2
    ready = await get_ready_work(async_session, project.id, learner_id)

    ready_ids = {task.id for task in ready}
    assert task1.id in ready_ids
    assert task3.id in ready_ids
    assert task2.id not in ready_ids  # Blocked by Task 1


@pytest.mark.asyncio
async def test_ready_work_lazy_initialization(async_session):
    """Test that ready work query works when learner has no progress records."""
    # Create learner without any progress records
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create tasks
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task1 = await create_task(
        async_session, TaskCreate(title="Task 1", task_type=TaskType.TASK, parent_id=project.id)
    )

    # Get ready work - should work even without progress records (COALESCE to 'open')
    ready = await get_ready_work(async_session, project.id, learner_id)

    assert len(ready) >= 1
    ready_ids = {task.id for task in ready}
    assert task1.id in ready_ids


@pytest.mark.asyncio
async def test_transitive_blocking_per_learner(async_session):
    """Test that blocking is transitive for a learner (A blocks B, B blocks C)."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create tasks
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task_a = await create_task(
        async_session, TaskCreate(title="Task A", task_type=TaskType.TASK, parent_id=project.id)
    )
    task_b = await create_task(
        async_session, TaskCreate(title="Task B", task_type=TaskType.TASK, parent_id=project.id)
    )
    task_c = await create_task(
        async_session, TaskCreate(title="Task C", task_type=TaskType.TASK, parent_id=project.id)
    )

    # A blocks B, B blocks C
    await add_dependency(async_session, task_b.id, task_a.id)
    await add_dependency(async_session, task_c.id, task_b.id)

    # Get ready work - should only include Task A
    ready = await get_ready_work(async_session, project.id, learner_id)

    ready_ids = {task.id for task in ready}
    assert task_a.id in ready_ids
    # Task B and C should not be ready (blocked transitively)
    assert task_b.id not in ready_ids
    assert task_c.id not in ready_ids


@pytest.mark.asyncio
async def test_multi_learner_independence(async_session):
    """Test that learner A closing task doesn't unblock it for learner B."""
    # Create two learners
    learner_a_id = generate_entity_id(PREFIX_LEARNER)
    learner_a = LearnerModel(id=learner_a_id, learner_metadata="{}")

    learner_b_id = generate_entity_id(PREFIX_LEARNER)
    learner_b = LearnerModel(id=learner_b_id, learner_metadata="{}")

    async_session.add_all([learner_a, learner_b])
    await async_session.commit()

    # Create tasks
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task1 = await create_task(
        async_session, TaskCreate(title="Task 1", task_type=TaskType.TASK, parent_id=project.id)
    )
    task2 = await create_task(
        async_session, TaskCreate(title="Task 2", task_type=TaskType.TASK, parent_id=project.id)
    )

    # Task 2 depends on Task 1
    await add_dependency(async_session, task2.id, task1.id)

    # Initially, both learners are blocked on Task 2
    assert await is_task_ready(async_session, task2.id, learner_a_id) is False
    assert await is_task_ready(async_session, task2.id, learner_b_id) is False

    # Learner A closes Task 1 (OPEN -> IN_PROGRESS -> CLOSED)
    from ltt.models import TaskStatus

    await update_status(async_session, task1.id, learner_a_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task1.id, learner_a_id, TaskStatus.CLOSED)

    # Task 2 is now ready for Learner A
    assert await is_task_ready(async_session, task2.id, learner_a_id) is True

    # But Task 2 is still blocked for Learner B
    assert await is_task_ready(async_session, task2.id, learner_b_id) is False


@pytest.mark.asyncio
async def test_get_blocked_tasks(async_session):
    """Test getting all blocked tasks with their blockers for a learner."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create tasks
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task1 = await create_task(
        async_session, TaskCreate(title="Task 1", task_type=TaskType.TASK, parent_id=project.id)
    )
    task2 = await create_task(
        async_session, TaskCreate(title="Task 2", task_type=TaskType.TASK, parent_id=project.id)
    )

    # Task 2 depends on Task 1
    await add_dependency(async_session, task2.id, task1.id)

    # Set Task 2 to blocked status for learner
    from ltt.models import TaskStatus

    await update_status(async_session, task2.id, learner_id, TaskStatus.BLOCKED)

    # Get blocked tasks
    blocked = await get_blocked_tasks(async_session, project.id, learner_id)

    assert len(blocked) == 1
    blocked_task, blockers = blocked[0]
    assert blocked_task.id == task2.id
    assert len(blockers) == 1
    assert blockers[0].id == task1.id


@pytest.mark.asyncio
async def test_ready_work_ordering(async_session):
    """Test that ready work is ordered correctly (in_progress, priority, depth, created_at)."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create tasks with different priorities (0-4 valid range)
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT, priority=0)
    )
    task_low = await create_task(
        async_session,
        TaskCreate(title="Low Priority", task_type=TaskType.TASK, parent_id=project.id, priority=4),
    )
    task_high = await create_task(
        async_session,
        TaskCreate(
            title="High Priority", task_type=TaskType.TASK, parent_id=project.id, priority=0
        ),
    )

    # Get ready work - high priority should come first
    ready = await get_ready_work(async_session, project.id, learner_id)

    assert len(ready) >= 2
    # High priority task should appear before low priority
    high_idx = next(i for i, t in enumerate(ready) if t.id == task_high.id)
    low_idx = next(i for i, t in enumerate(ready) if t.id == task_low.id)
    assert high_idx < low_idx


@pytest.mark.asyncio
async def test_ready_work_with_task_type_filter(async_session):
    """Test filtering ready work by task type."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create tasks of different types
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    epic = await create_task(
        async_session, TaskCreate(title="Epic", task_type=TaskType.EPIC, parent_id=project.id)
    )
    await create_task(
        async_session, TaskCreate(title="Task", task_type=TaskType.TASK, parent_id=epic.id)
    )

    # Get ready work filtered by TASK type
    ready = await get_ready_work(async_session, project.id, learner_id, task_type="task")

    assert len(ready) >= 1
    for t in ready:
        assert t.task_type == TaskType.TASK


@pytest.mark.asyncio
async def test_related_dependency_does_not_block(async_session):
    """Test that RELATED dependencies don't block tasks."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create tasks
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task1 = await create_task(
        async_session, TaskCreate(title="Task 1", task_type=TaskType.TASK, parent_id=project.id)
    )
    task2 = await create_task(
        async_session, TaskCreate(title="Task 2", task_type=TaskType.TASK, parent_id=project.id)
    )

    # Task 2 has RELATED dependency on Task 1 (not blocking)
    await add_dependency(async_session, task2.id, task1.id, DependencyType.RELATED)

    # Task 2 should still be ready (not blocked)
    assert await is_task_ready(async_session, task2.id, learner_id) is True

    # Both tasks should appear in ready work
    ready = await get_ready_work(async_session, project.id, learner_id)
    ready_ids = {task.id for task in ready}
    assert task1.id in ready_ids
    assert task2.id in ready_ids
