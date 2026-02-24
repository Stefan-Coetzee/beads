"""
Tests for feedback tools (add_comment, get_comments).
"""

import pytest
from ltt.models import LearnerModel, TaskCreate, TaskType
from ltt.services.task_service import create_task
from ltt.tools.feedback import add_comment, get_comments
from ltt.tools.schemas import AddCommentInput, GetCommentsInput
from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id


@pytest.mark.asyncio
async def test_add_comment(async_session):
    """Test adding a comment to a task."""
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

    # Add comment
    result = await add_comment(
        AddCommentInput(task_id=task.id, comment="This is a test comment"),
        learner_id,
        async_session,
    )

    assert result.id is not None
    assert result.author == learner_id
    assert result.text == "This is a test comment"
    assert result.created_at is not None


@pytest.mark.asyncio
async def test_get_comments(async_session):
    """Test getting comments for a task."""
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

    # Add comments
    await add_comment(
        AddCommentInput(task_id=task.id, comment="First comment"),
        learner_id,
        async_session,
    )
    await add_comment(
        AddCommentInput(task_id=task.id, comment="Second comment"),
        learner_id,
        async_session,
    )

    # Get comments
    result = await get_comments(GetCommentsInput(task_id=task.id), learner_id, async_session)

    assert result.total == 2
    assert len(result.comments) == 2
    assert result.comments[0].text == "First comment"
    assert result.comments[1].text == "Second comment"


@pytest.mark.asyncio
async def test_get_comments_respects_limit(async_session):
    """Test get_comments respects limit parameter."""
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

    # Add multiple comments
    for i in range(5):
        await add_comment(
            AddCommentInput(task_id=task.id, comment=f"Comment {i}"),
            learner_id,
            async_session,
        )

    # Get comments with limit
    result = await get_comments(
        GetCommentsInput(task_id=task.id, limit=2), learner_id, async_session
    )

    assert len(result.comments) == 2
    assert result.total == 2  # Total reflects the limited count


@pytest.mark.asyncio
async def test_get_comments_empty(async_session):
    """Test getting comments when there are none."""
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

    # Get comments (none exist)
    result = await get_comments(GetCommentsInput(task_id=task.id), learner_id, async_session)

    assert result.total == 0
    assert len(result.comments) == 0


@pytest.mark.asyncio
async def test_comments_are_learner_scoped(async_session):
    """Test that comments are scoped to learner (private comments)."""
    # Create two learners
    learner1_id = generate_entity_id(PREFIX_LEARNER)
    learner1 = LearnerModel(id=learner1_id, learner_metadata="{}")
    async_session.add(learner1)

    learner2_id = generate_entity_id(PREFIX_LEARNER)
    learner2 = LearnerModel(id=learner2_id, learner_metadata="{}")
    async_session.add(learner2)

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

    # Learner 1 adds a comment
    await add_comment(
        AddCommentInput(task_id=task.id, comment="Learner 1 comment"),
        learner1_id,
        async_session,
    )

    # Learner 2 adds a comment
    await add_comment(
        AddCommentInput(task_id=task.id, comment="Learner 2 comment"),
        learner2_id,
        async_session,
    )

    # Learner 1 should only see their own private comment
    result1 = await get_comments(GetCommentsInput(task_id=task.id), learner1_id, async_session)
    # Learner 2 should only see their own private comment
    result2 = await get_comments(GetCommentsInput(task_id=task.id), learner2_id, async_session)

    # Each learner should only see their own comment (private to them)
    assert result1.total == 1
    assert result1.comments[0].text == "Learner 1 comment"

    assert result2.total == 1
    assert result2.comments[0].text == "Learner 2 comment"
