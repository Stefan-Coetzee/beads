"""
Tests for progress tools (start_task, submit).
"""

import pytest
from ltt.models import (
    DependencyType,
    LearnerModel,
    TaskCreate,
    TaskStatus,
    TaskType,
)
from ltt.services.dependency_service import add_dependency
from ltt.services.progress_service import update_status
from ltt.services.task_service import create_task
from ltt.tools.progress import start_task, submit
from ltt.tools.schemas import StartTaskInput, SubmitInput
from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id


@pytest.mark.asyncio
async def test_start_task_sets_status(async_session):
    """Test start_task sets status to in_progress."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and task
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )

    # Start task
    result = await start_task(StartTaskInput(task_id=task.id), learner_id, async_session)

    assert result.success is True
    assert result.task_id == task.id
    assert result.status == "in_progress"
    assert result.context is not None
    assert result.context.status == "in_progress"


@pytest.mark.asyncio
async def test_start_task_returns_context(async_session):
    """Test start_task returns full task context."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and task
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task",
            task_type=TaskType.TASK,
            description="Test task",
            parent_id=project.id,
            project_id=project.id,
        ),
    )

    # Start task
    result = await start_task(StartTaskInput(task_id=task.id), learner_id, async_session)

    assert result.context.task_id == task.id
    assert result.context.title == "Task"
    assert result.context.description == "Test task"
    # No project_id or progress in simplified context


@pytest.mark.asyncio
async def test_start_task_fails_if_blocked(async_session):
    """Test start_task fails if task is blocked."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project with tasks
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task1 = await create_task(
        async_session,
        TaskCreate(
            title="Task 1", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )
    task2 = await create_task(
        async_session,
        TaskCreate(
            title="Task 2", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )

    # task2 depends on task1
    await add_dependency(async_session, task2.id, task1.id, DependencyType.BLOCKS)

    # Try to start blocked task
    result = await start_task(StartTaskInput(task_id=task2.id), learner_id, async_session)

    assert result.success is False
    assert "blocked" in result.message.lower()
    assert result.context is None


@pytest.mark.asyncio
async def test_start_task_fails_if_closed(async_session):
    """Test start_task fails if task is already closed."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and task
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )

    # Close task
    await update_status(async_session, task.id, learner_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task.id, learner_id, TaskStatus.CLOSED)

    # Try to start closed task
    result = await start_task(StartTaskInput(task_id=task.id), learner_id, async_session)

    assert result.success is False
    assert "closed" in result.message.lower()
    assert result.context is None


@pytest.mark.asyncio
async def test_submit_creates_submission(async_session):
    """Test submit creates a submission."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and task
    project = await create_task(
        async_session,
        TaskCreate(title="Project", task_type=TaskType.PROJECT, acceptance_criteria="Complete"),
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
            acceptance_criteria="Submit work",
        ),
    )

    # Start the task first (required before submit)
    await start_task(StartTaskInput(task_id=task.id), learner_id, async_session)

    # Submit work
    result = await submit(
        SubmitInput(task_id=task.id, content="my code", submission_type="code"),
        learner_id,
        async_session,
    )

    assert result.success is True
    assert result.submission_id is not None
    assert result.attempt_number == 1
    assert result.validation_passed is not None


@pytest.mark.asyncio
async def test_submit_validates_automatically(async_session):
    """Test submit triggers automatic validation."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and task
    project = await create_task(
        async_session,
        TaskCreate(title="Project", task_type=TaskType.PROJECT, acceptance_criteria="Complete"),
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
            acceptance_criteria="Submit work",
        ),
    )

    # Start task first (required for proper workflow)
    await start_task(StartTaskInput(task_id=task.id), learner_id, async_session)

    # Submit work
    result = await submit(
        SubmitInput(task_id=task.id, content="my work", submission_type="text"),
        learner_id,
        async_session,
    )

    # Should have validation result
    assert result.validation_passed is not None
    assert result.status is not None
    if result.validation_passed:
        assert "successful" in result.message.lower() or "complete" in result.message.lower()
    else:
        assert "failed" in result.message.lower()


@pytest.mark.asyncio
async def test_submit_auto_closes_task_on_success(async_session):
    """Test submit auto-closes task when validation passes (ADR-002)."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and task
    project = await create_task(
        async_session,
        TaskCreate(title="Project", task_type=TaskType.PROJECT),
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
            acceptance_criteria="Submit any work",
        ),
    )

    # Start task (moves to in_progress)
    start_result = await start_task(StartTaskInput(task_id=task.id), learner_id, async_session)
    assert start_result.status == "in_progress"

    # Submit work (should auto-close on success)
    result = await submit(
        SubmitInput(task_id=task.id, content="my completed work", submission_type="text"),
        learner_id,
        async_session,
    )

    assert result.success is True
    assert result.validation_passed is True
    assert result.status == "closed"
    assert "complete" in result.message.lower()


@pytest.mark.asyncio
async def test_submit_auto_closes_subtask_on_success(async_session):
    """Test submit auto-closes subtask when validation passes."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create hierarchy: project > epic > task > subtask
    project = await create_task(
        async_session,
        TaskCreate(title="Project", task_type=TaskType.PROJECT),
    )
    epic = await create_task(
        async_session,
        TaskCreate(
            title="Epic",
            task_type=TaskType.EPIC,
            parent_id=project.id,
            project_id=project.id,
        ),
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task",
            task_type=TaskType.TASK,
            parent_id=epic.id,
            project_id=project.id,
        ),
    )
    subtask = await create_task(
        async_session,
        TaskCreate(
            title="Subtask",
            task_type=TaskType.SUBTASK,
            parent_id=task.id,
            project_id=project.id,
            acceptance_criteria="Write the code",
        ),
    )

    # Start subtask
    await start_task(StartTaskInput(task_id=subtask.id), learner_id, async_session)

    # Submit work
    result = await submit(
        SubmitInput(
            task_id=subtask.id, content="def hello(): return 'world'", submission_type="code"
        ),
        learner_id,
        async_session,
    )

    assert result.success is True
    assert result.validation_passed is True
    assert result.status == "closed"
    assert "complete" in result.message.lower()


@pytest.mark.asyncio
async def test_submit_increments_attempt_number(async_session):
    """Test submit increments attempt number."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and task
    project = await create_task(
        async_session,
        TaskCreate(title="Project", task_type=TaskType.PROJECT, acceptance_criteria="Complete"),
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
            acceptance_criteria="Submit work",
        ),
    )

    # Start task first (required before submit)
    await start_task(StartTaskInput(task_id=task.id), learner_id, async_session)

    # First submission (will auto-close task on success)
    result1 = await submit(
        SubmitInput(task_id=task.id, content="attempt 1", submission_type="text"),
        learner_id,
        async_session,
    )

    # Reopen task using go_back (task is now closed after first submit)
    from ltt.tools.control import GoBackInput, go_back

    await go_back(
        GoBackInput(task_id=task.id, reason="Need to resubmit"), learner_id, async_session
    )

    # Start task again
    await start_task(StartTaskInput(task_id=task.id), learner_id, async_session)

    # Second submission
    result2 = await submit(
        SubmitInput(task_id=task.id, content="attempt 2", submission_type="text"),
        learner_id,
        async_session,
    )

    assert result1.attempt_number == 1
    assert result2.attempt_number == 2


@pytest.mark.asyncio
async def test_submit_invalid_type(async_session):
    """Test submit with invalid submission type."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and task
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )

    # Start task first (required before submit)
    await start_task(StartTaskInput(task_id=task.id), learner_id, async_session)

    # Submit with invalid type
    result = await submit(
        SubmitInput(task_id=task.id, content="work", submission_type="invalid_type"),
        learner_id,
        async_session,
    )

    assert result.success is False
    assert "invalid" in result.message.lower()
