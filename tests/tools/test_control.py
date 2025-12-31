"""
Tests for control tools (go_back, request_help).
"""

import pytest

from ltt.models import LearnerModel, TaskCreate, TaskStatus, TaskType
from ltt.services.progress_service import update_status
from ltt.services.task_service import create_task
from ltt.tools.control import go_back, request_help
from ltt.tools.feedback import get_comments
from ltt.tools.schemas import GetCommentsInput, GoBackInput, RequestHelpInput
from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id


@pytest.mark.asyncio
async def test_go_back_reopens_closed_task(async_session):
    """Test go_back reopens a closed task."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and task
    project = await create_task(async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT))
    task = await create_task(
        async_session,
        TaskCreate(title="Task", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id),
    )

    # Close task
    await update_status(async_session, task.id, learner_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task.id, learner_id, TaskStatus.CLOSED)

    # Reopen task
    result = await go_back(
        GoBackInput(task_id=task.id, reason="Need to revise approach"),
        learner_id,
        async_session,
    )

    assert result.success is True
    assert result.task_id == task.id
    assert result.new_status == "open"
    assert result.message == "Task reopened: Need to revise approach"
    assert result.reason == "Need to revise approach"


@pytest.mark.asyncio
async def test_go_back_fails_if_not_closed(async_session):
    """Test go_back fails if task is not closed."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and task
    project = await create_task(async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT))
    task = await create_task(
        async_session,
        TaskCreate(title="Task", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id),
    )

    # Task is open (not closed)
    # Try to reopen
    result = await go_back(
        GoBackInput(task_id=task.id, reason="Try to reopen"),
        learner_id,
        async_session,
    )

    assert result.success is False
    assert "not closed" in result.message.lower()


@pytest.mark.asyncio
async def test_go_back_requires_reason(async_session):
    """Test go_back requires a reason."""
    # This is validated by Pydantic, so we test that the schema enforces it
    with pytest.raises(Exception):  # Pydantic ValidationError
        GoBackInput(task_id="task-123")  # Missing required reason field


@pytest.mark.asyncio
async def test_request_help_creates_comment(async_session):
    """Test request_help creates a help request comment."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and task
    project = await create_task(async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT))
    task = await create_task(
        async_session,
        TaskCreate(title="Task", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id),
    )

    # Request help
    result = await request_help(
        RequestHelpInput(task_id=task.id, message="I'm stuck on this validation error"),
        learner_id,
        async_session,
    )

    assert result.request_id is not None
    assert "submitted" in result.message.lower()


@pytest.mark.asyncio
async def test_request_help_comment_is_tagged(async_session):
    """Test request_help comment is tagged with [HELP REQUEST]."""
    # Create learner
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Create project and task
    project = await create_task(async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT))
    task = await create_task(
        async_session,
        TaskCreate(title="Task", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id),
    )

    # Request help
    await request_help(
        RequestHelpInput(task_id=task.id, message="Need help with API"),
        learner_id,
        async_session,
    )

    # Get comments
    comments = await get_comments(GetCommentsInput(task_id=task.id), learner_id, async_session)

    assert comments.total == 1
    assert "[HELP REQUEST]" in comments.comments[0].text
    assert "Need help with API" in comments.comments[0].text


@pytest.mark.asyncio
async def test_go_back_is_learner_scoped(async_session):
    """Test go_back only affects the learner's progress."""
    # Create two learners
    learner1_id = generate_entity_id(PREFIX_LEARNER)
    learner1 = LearnerModel(id=learner1_id, learner_metadata="{}")
    async_session.add(learner1)

    learner2_id = generate_entity_id(PREFIX_LEARNER)
    learner2 = LearnerModel(id=learner2_id, learner_metadata="{}")
    async_session.add(learner2)

    await async_session.commit()

    # Create project and task
    project = await create_task(async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT))
    task = await create_task(
        async_session,
        TaskCreate(title="Task", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id),
    )

    # Both learners close the task
    await update_status(async_session, task.id, learner1_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task.id, learner1_id, TaskStatus.CLOSED)
    await update_status(async_session, task.id, learner2_id, TaskStatus.IN_PROGRESS)
    await update_status(async_session, task.id, learner2_id, TaskStatus.CLOSED)

    # Learner 1 reopens the task
    result1 = await go_back(
        GoBackInput(task_id=task.id, reason="Need to redo"),
        learner1_id,
        async_session,
    )

    assert result1.success is True
    assert result1.new_status == "open"

    # Learner 2's task should still be closed
    # Try to reopen learner 2's task from closed state (should succeed)
    result2 = await go_back(
        GoBackInput(task_id=task.id, reason="Also need to redo"),
        learner2_id,
        async_session,
    )

    # Both learners should have successfully reopened their own progress
    assert result2.success is True
    assert result2.new_status == "open"
