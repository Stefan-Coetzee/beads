"""
Tests for progress and status management service.
"""

import pytest
from ltt.models import LearnerModel, TaskCreate, TaskStatus, TaskType
from ltt.services.progress_service import (
    InvalidStatusTransitionError,
    TaskNotFoundError,
    close_task,
    get_learner_tasks_by_status,
    get_or_create_progress,
    get_progress,
    reopen_task,
    start_task,
    update_status,
)
from ltt.services.task_service import create_task
from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id


@pytest.mark.asyncio
async def test_get_or_create_progress_new(async_session):
    """Test lazy initialization of progress record."""
    # Create task
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Get or create progress (should create new)
    progress = await get_or_create_progress(async_session, task.id, learner_id)

    assert progress.task_id == task.id
    assert progress.learner_id == learner_id
    assert progress.status == TaskStatus.OPEN.value
    assert progress.started_at is None
    assert progress.completed_at is None


@pytest.mark.asyncio
async def test_get_or_create_progress_existing(async_session):
    """Test that getting existing progress doesn't create duplicate."""
    # Create task and learner
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create progress record
    progress1 = await get_or_create_progress(async_session, task.id, learner_id)
    await async_session.commit()

    # Get again (should return same)
    progress2 = await get_or_create_progress(async_session, task.id, learner_id)

    assert progress1.id == progress2.id


@pytest.mark.asyncio
async def test_start_task(async_session):
    """Test starting a task (open -> in_progress)."""
    # Create task and learner
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Start task
    progress = await start_task(async_session, task.id, learner_id)

    assert progress.status == TaskStatus.IN_PROGRESS
    assert progress.started_at is not None
    assert progress.completed_at is None


@pytest.mark.asyncio
async def test_close_task(async_session):
    """Test closing a task (in_progress -> closed)."""
    # Create task and learner
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Start then close task
    await start_task(async_session, task.id, learner_id)
    progress = await close_task(async_session, task.id, learner_id, "Completed successfully")

    assert progress.status == TaskStatus.CLOSED
    assert progress.completed_at is not None
    assert progress.close_reason == "Completed successfully"


@pytest.mark.asyncio
async def test_reopen_task(async_session):
    """Test reopening a closed task (closed -> open)."""
    # Create task and learner
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Start, close, then reopen
    await start_task(async_session, task.id, learner_id)
    await close_task(async_session, task.id, learner_id, "Done")
    progress = await reopen_task(async_session, task.id, learner_id)

    assert progress.status == TaskStatus.OPEN
    assert progress.completed_at is None
    assert progress.close_reason is None


@pytest.mark.asyncio
async def test_invalid_status_transition(async_session):
    """Test that invalid status transitions are rejected."""
    # Create task and learner
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Try to close from open (invalid - must be in_progress first)
    with pytest.raises(InvalidStatusTransitionError):
        await update_status(async_session, task.id, learner_id, TaskStatus.CLOSED)


@pytest.mark.asyncio
async def test_cannot_close_parent_with_open_children(async_session):
    """Test that parent cannot be closed if children are not closed."""
    # Create parent and child
    parent_data = TaskCreate(title="Parent", task_type=TaskType.PROJECT)
    parent = await create_task(async_session, parent_data)

    child_data = TaskCreate(title="Child", task_type=TaskType.EPIC, parent_id=parent.id)
    await create_task(async_session, child_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Start parent
    await start_task(async_session, parent.id, learner_id)

    # Try to close parent while child is still open
    with pytest.raises(InvalidStatusTransitionError, match="child .* is still"):
        await close_task(async_session, parent.id, learner_id, "Done")


@pytest.mark.asyncio
async def test_can_close_parent_when_children_closed(async_session):
    """Test that parent can be closed when all children are closed."""
    # Create parent and child
    parent_data = TaskCreate(title="Parent", task_type=TaskType.PROJECT)
    parent = await create_task(async_session, parent_data)

    child_data = TaskCreate(title="Child", task_type=TaskType.EPIC, parent_id=parent.id)
    child = await create_task(async_session, child_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Close child first
    await start_task(async_session, child.id, learner_id)
    await close_task(async_session, child.id, learner_id, "Child done")

    # Now close parent (should succeed)
    await start_task(async_session, parent.id, learner_id)
    progress = await close_task(async_session, parent.id, learner_id, "Parent done")

    assert progress.status == TaskStatus.CLOSED


@pytest.mark.asyncio
async def test_get_learner_tasks_by_status(async_session):
    """Test retrieving tasks by status for a learner."""
    # Create tasks
    task1_data = TaskCreate(title="Task 1", task_type=TaskType.PROJECT)
    task1 = await create_task(async_session, task1_data)

    task2_data = TaskCreate(title="Task 2", task_type=TaskType.PROJECT)
    task2 = await create_task(async_session, task2_data)

    task3_data = TaskCreate(title="Task 3", task_type=TaskType.PROJECT)
    task3 = await create_task(async_session, task3_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Set different statuses
    await start_task(async_session, task1.id, learner_id)  # in_progress
    await start_task(async_session, task2.id, learner_id)  # in_progress
    await start_task(async_session, task3.id, learner_id)
    await close_task(async_session, task3.id, learner_id, "Done")  # closed

    # Get in_progress tasks
    in_progress_tasks = await get_learner_tasks_by_status(
        async_session, learner_id, TaskStatus.IN_PROGRESS
    )

    assert len(in_progress_tasks) == 2
    task_titles = {task.title for task, _ in in_progress_tasks}
    assert task_titles == {"Task 1", "Task 2"}

    # Get closed tasks
    closed_tasks = await get_learner_tasks_by_status(async_session, learner_id, TaskStatus.CLOSED)

    assert len(closed_tasks) == 1
    assert closed_tasks[0][0].title == "Task 3"


@pytest.mark.asyncio
async def test_update_status_nonexistent_task(async_session):
    """Test that updating status for nonexistent task fails."""
    learner_id = generate_entity_id(PREFIX_LEARNER)

    with pytest.raises(TaskNotFoundError):
        await update_status(async_session, "nonexistent-id", learner_id, TaskStatus.IN_PROGRESS)


@pytest.mark.asyncio
async def test_get_progress_none_when_not_exists(async_session):
    """Test that get_progress returns None when no record exists."""
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)

    progress = await get_progress(async_session, task.id, learner_id)

    assert progress is None


# ─────────────────────────────────────────────────────────────
# Comprehensive Status Transition Tests
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transition_open_to_blocked(async_session):
    """Test valid transition from OPEN to BLOCKED."""
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # OPEN → BLOCKED (valid)
    progress = await update_status(async_session, task.id, learner_id, TaskStatus.BLOCKED)

    assert progress.status == TaskStatus.BLOCKED
    assert progress.started_at is None  # Never started
    assert progress.completed_at is None


@pytest.mark.asyncio
async def test_transition_in_progress_to_blocked(async_session):
    """Test valid transition from IN_PROGRESS to BLOCKED."""
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Start task first
    await start_task(async_session, task.id, learner_id)

    # IN_PROGRESS → BLOCKED (valid)
    progress = await update_status(async_session, task.id, learner_id, TaskStatus.BLOCKED)

    assert progress.status == TaskStatus.BLOCKED
    assert progress.started_at is not None  # Was started
    assert progress.completed_at is None


@pytest.mark.asyncio
async def test_transition_blocked_to_open(async_session):
    """Test valid transition from BLOCKED to OPEN."""
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Block the task first
    await update_status(async_session, task.id, learner_id, TaskStatus.BLOCKED)

    # BLOCKED → OPEN (valid)
    progress = await update_status(async_session, task.id, learner_id, TaskStatus.OPEN)

    assert progress.status == TaskStatus.OPEN


@pytest.mark.asyncio
async def test_transition_blocked_to_in_progress(async_session):
    """Test valid transition from BLOCKED to IN_PROGRESS."""
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Block the task first
    await update_status(async_session, task.id, learner_id, TaskStatus.BLOCKED)

    # BLOCKED → IN_PROGRESS (valid)
    progress = await update_status(async_session, task.id, learner_id, TaskStatus.IN_PROGRESS)

    assert progress.status == TaskStatus.IN_PROGRESS
    assert progress.started_at is not None  # Sets started_at


@pytest.mark.asyncio
async def test_transition_blocked_to_closed_forbidden(async_session):
    """Test invalid transition from BLOCKED to CLOSED."""
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Block the task first
    await update_status(async_session, task.id, learner_id, TaskStatus.BLOCKED)

    # BLOCKED → CLOSED (invalid)
    with pytest.raises(
        InvalidStatusTransitionError, match="Cannot transition from blocked to closed"
    ):
        await update_status(async_session, task.id, learner_id, TaskStatus.CLOSED)


@pytest.mark.asyncio
async def test_transition_closed_to_in_progress_forbidden(async_session):
    """Test invalid transition from CLOSED to IN_PROGRESS."""
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Close the task
    await start_task(async_session, task.id, learner_id)
    await close_task(async_session, task.id, learner_id, "Done")

    # CLOSED → IN_PROGRESS (invalid - can only reopen to OPEN)
    with pytest.raises(
        InvalidStatusTransitionError, match="Cannot transition from closed to in_progress"
    ):
        await update_status(async_session, task.id, learner_id, TaskStatus.IN_PROGRESS)


@pytest.mark.asyncio
async def test_transition_closed_to_blocked_forbidden(async_session):
    """Test invalid transition from CLOSED to BLOCKED."""
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Close the task
    await start_task(async_session, task.id, learner_id)
    await close_task(async_session, task.id, learner_id, "Done")

    # CLOSED → BLOCKED (invalid)
    with pytest.raises(
        InvalidStatusTransitionError, match="Cannot transition from closed to blocked"
    ):
        await update_status(async_session, task.id, learner_id, TaskStatus.BLOCKED)


@pytest.mark.asyncio
async def test_start_task_already_in_progress(async_session):
    """Test starting a task that's already in progress (should succeed - idempotent)."""
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Start task
    await start_task(async_session, task.id, learner_id)

    # Start again (IN_PROGRESS → IN_PROGRESS is not in VALID_TRANSITIONS)
    # This should raise an error since the task is already in_progress
    with pytest.raises(
        InvalidStatusTransitionError, match="Cannot transition from in_progress to in_progress"
    ):
        await start_task(async_session, task.id, learner_id)


@pytest.mark.asyncio
async def test_reopen_task_clears_completion_data(async_session):
    """Test that reopening a task clears completed_at and close_reason."""
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Complete the task
    await start_task(async_session, task.id, learner_id)
    await close_task(async_session, task.id, learner_id, "Initial completion")

    # Reopen it
    progress = await reopen_task(async_session, task.id, learner_id)

    assert progress.status == TaskStatus.OPEN
    assert progress.completed_at is None
    assert progress.close_reason is None
    assert progress.started_at is not None  # Still has started_at


@pytest.mark.asyncio
async def test_transition_open_to_in_progress_sets_started_at(async_session):
    """Test that OPEN → IN_PROGRESS sets started_at timestamp."""
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Verify initial state
    initial_progress = await get_or_create_progress(async_session, task.id, learner_id)
    assert initial_progress.started_at is None

    # Start task
    progress = await start_task(async_session, task.id, learner_id)

    assert progress.started_at is not None
    assert progress.completed_at is None


@pytest.mark.asyncio
async def test_transition_in_progress_to_closed_sets_completed_at(async_session):
    """Test that IN_PROGRESS → CLOSED sets completed_at timestamp."""
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    await start_task(async_session, task.id, learner_id)

    # Close task
    progress = await close_task(async_session, task.id, learner_id, "Task completed")

    assert progress.completed_at is not None
    assert progress.close_reason == "Task completed"
    assert progress.status == TaskStatus.CLOSED
