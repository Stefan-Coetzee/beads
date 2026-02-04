"""
Tests for task management service.
"""

import pytest
from sqlalchemy import select

from ltt.models import CommentCreate, TaskCreate, TaskModel, TaskType, TaskUpdate
from ltt.services.task_service import (
    InvalidTaskHierarchyError,
    TaskNotFoundError,
    add_comment,
    create_task,
    delete_task,
    get_ancestors,
    get_children,
    get_comments,
    get_task,
    get_task_count,
    update_task,
)


@pytest.mark.asyncio
async def test_create_project_task(async_session):
    """Test creating a project (root task)."""
    task_data = TaskCreate(
        title="Build E-commerce Site",
        description="A full-stack e-commerce platform",
        task_type=TaskType.PROJECT,
    )

    task = await create_task(async_session, task_data)

    assert task.id.startswith("proj-")
    assert task.title == "Build E-commerce Site"
    assert task.task_type == TaskType.PROJECT
    assert task.project_id == task.id  # Project ID should be itself
    assert task.parent_id is None


@pytest.mark.asyncio
async def test_create_child_task(async_session):
    """Test creating a task with a parent."""
    # Create project
    project_data = TaskCreate(
        title="My Project",
        task_type=TaskType.PROJECT,
    )
    project = await create_task(async_session, project_data)

    # Create epic under project
    epic_data = TaskCreate(
        title="Build Backend",
        description="Create FastAPI backend",
        task_type=TaskType.EPIC,
        parent_id=project.id,
    )
    epic = await create_task(async_session, epic_data)

    assert epic.id.startswith(f"{project.id}.")
    assert epic.parent_id == project.id
    assert epic.project_id == project.id
    assert epic.title == "Build Backend"


@pytest.mark.asyncio
async def test_create_task_invalid_parent(async_session):
    """Test that creating a task with non-existent parent fails."""
    task_data = TaskCreate(
        title="Orphan Task",
        parent_id="nonexistent-id",
        task_type=TaskType.TASK,
    )

    with pytest.raises(InvalidTaskHierarchyError, match="does not exist"):
        await create_task(async_session, task_data)


@pytest.mark.asyncio
async def test_get_task(async_session):
    """Test retrieving a task by ID."""
    task_data = TaskCreate(title="Test Task", task_type=TaskType.PROJECT)
    created_task = await create_task(async_session, task_data)

    retrieved_task = await get_task(async_session, created_task.id)

    assert retrieved_task.id == created_task.id
    assert retrieved_task.title == "Test Task"


@pytest.mark.asyncio
async def test_get_task_not_found(async_session):
    """Test that getting non-existent task raises error."""
    with pytest.raises(TaskNotFoundError):
        await get_task(async_session, "nonexistent-id")


@pytest.mark.asyncio
async def test_update_task(async_session):
    """Test updating task fields."""
    task_data = TaskCreate(title="Original Title", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    updates = TaskUpdate(
        title="Updated Title",
        description="New description",
        priority=4,
    )
    updated_task = await update_task(async_session, task.id, updates)

    assert updated_task.title == "Updated Title"
    assert updated_task.description == "New description"
    assert updated_task.priority == 4


@pytest.mark.asyncio
async def test_delete_task(async_session):
    """Test deleting a task."""
    task_data = TaskCreate(title="To Delete", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    await delete_task(async_session, task.id)

    # Verify task is deleted
    result = await async_session.execute(select(TaskModel).where(TaskModel.id == task.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_get_children(async_session):
    """Test retrieving child tasks."""
    # Create parent
    parent_data = TaskCreate(title="Parent", task_type=TaskType.PROJECT)
    parent = await create_task(async_session, parent_data)

    # Create children
    child1_data = TaskCreate(title="Child 1", task_type=TaskType.EPIC, parent_id=parent.id)
    await create_task(async_session, child1_data)

    child2_data = TaskCreate(title="Child 2", task_type=TaskType.EPIC, parent_id=parent.id)
    await create_task(async_session, child2_data)

    # Get children
    children = await get_children(async_session, parent.id)

    assert len(children) == 2
    child_titles = {child.title for child in children}
    assert child_titles == {"Child 1", "Child 2"}


@pytest.mark.asyncio
async def test_get_children_recursive(async_session):
    """Test retrieving all descendants recursively."""
    # Create hierarchy: project -> epic -> task -> subtask
    project_data = TaskCreate(title="Project", task_type=TaskType.PROJECT)
    project = await create_task(async_session, project_data)

    epic_data = TaskCreate(title="Epic", task_type=TaskType.EPIC, parent_id=project.id)
    epic = await create_task(async_session, epic_data)

    task_data = TaskCreate(title="Task", task_type=TaskType.TASK, parent_id=epic.id)
    task = await create_task(async_session, task_data)

    subtask_data = TaskCreate(title="Subtask", task_type=TaskType.SUBTASK, parent_id=task.id)
    await create_task(async_session, subtask_data)

    # Get all descendants from project
    descendants = await get_children(async_session, project.id, recursive=True)

    assert len(descendants) == 3
    descendant_titles = {d.title for d in descendants}
    assert descendant_titles == {"Epic", "Task", "Subtask"}


@pytest.mark.asyncio
async def test_get_ancestors(async_session):
    """Test retrieving ancestor tasks."""
    # Create hierarchy
    project_data = TaskCreate(title="Project", task_type=TaskType.PROJECT)
    project = await create_task(async_session, project_data)

    epic_data = TaskCreate(title="Epic", task_type=TaskType.EPIC, parent_id=project.id)
    epic = await create_task(async_session, epic_data)

    task_data = TaskCreate(title="Task", task_type=TaskType.TASK, parent_id=epic.id)
    task = await create_task(async_session, task_data)

    # Get ancestors from task
    ancestors = await get_ancestors(async_session, task.id)

    assert len(ancestors) == 2
    assert ancestors[0].title == "Epic"  # Nearest first
    assert ancestors[1].title == "Project"  # Root last


@pytest.mark.asyncio
async def test_add_comment(async_session):
    """Test adding a comment to a task."""
    task_data = TaskCreate(title="Task with Comment", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    comment_data = CommentCreate(
        task_id=task.id,
        author="user-123",
        text="This is a comment",
    )
    comment = await add_comment(async_session, task.id, comment_data)

    assert comment.task_id == task.id
    assert comment.author == "user-123"
    assert comment.text == "This is a comment"


@pytest.mark.asyncio
async def test_get_comments_shared_only(async_session):
    """Test retrieving shared comments."""
    from ltt.models import LearnerModel
    from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id

    task_data = TaskCreate(title="Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    # Create learner for private comment
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata="{}")
    async_session.add(learner)
    await async_session.commit()

    # Add shared comment (no learner_id)
    shared_comment = CommentCreate(
        task_id=task.id,
        author="tutor",
        text="Shared comment",
    )
    await add_comment(async_session, task.id, shared_comment)

    # Add private comment
    private_comment = CommentCreate(
        task_id=task.id,
        author="learner-1",
        text="Private comment",
        learner_id=learner_id,
    )
    await add_comment(async_session, task.id, private_comment)

    # Get comments without learner_id (should only get shared)
    comments = await get_comments(async_session, task.id)

    assert len(comments) == 1
    assert comments[0].text == "Shared comment"


@pytest.mark.asyncio
async def test_get_comments_with_learner(async_session):
    """Test retrieving comments including private ones for a learner."""
    from ltt.models import LearnerModel
    from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id

    task_data = TaskCreate(title="Task", task_type=TaskType.PROJECT)
    task = await create_task(async_session, task_data)

    # Create learners
    learner_id_1 = generate_entity_id(PREFIX_LEARNER)
    learner1 = LearnerModel(id=learner_id_1, learner_metadata="{}")
    async_session.add(learner1)

    learner_id_2 = generate_entity_id(PREFIX_LEARNER)
    learner2 = LearnerModel(id=learner_id_2, learner_metadata="{}")
    async_session.add(learner2)

    await async_session.commit()

    # Add shared comment
    shared_comment = CommentCreate(
        task_id=task.id,
        author="tutor",
        text="Shared comment",
    )
    await add_comment(async_session, task.id, shared_comment)

    # Add private comment for learner-1
    private_comment_1 = CommentCreate(
        task_id=task.id,
        author="learner-1",
        text="Private for learner 1",
        learner_id=learner_id_1,
    )
    await add_comment(async_session, task.id, private_comment_1)

    # Add private comment for learner-2
    private_comment_2 = CommentCreate(
        task_id=task.id,
        author="learner-2",
        text="Private for learner 2",
        learner_id=learner_id_2,
    )
    await add_comment(async_session, task.id, private_comment_2)

    # Get comments for learner-1
    comments = await get_comments(async_session, task.id, learner_id=learner_id_1)

    assert len(comments) == 2
    comment_texts = {c.text for c in comments}
    assert comment_texts == {"Shared comment", "Private for learner 1"}


@pytest.mark.asyncio
async def test_get_task_count(async_session):
    """Test counting tasks."""
    # Create tasks in different projects
    proj1_data = TaskCreate(title="Project 1", task_type=TaskType.PROJECT)
    proj1 = await create_task(async_session, proj1_data)

    proj2_data = TaskCreate(title="Project 2", task_type=TaskType.PROJECT)
    await create_task(async_session, proj2_data)

    task1_data = TaskCreate(title="Task 1", task_type=TaskType.TASK, parent_id=proj1.id)
    await create_task(async_session, task1_data)

    # Total count
    total = await get_task_count(async_session)
    assert total == 3

    # Count for project 1
    proj1_count = await get_task_count(async_session, project_id=proj1.id)
    assert proj1_count == 2  # Project + 1 task
