"""
Tests for learning content service.
"""

import pytest
from ltt.models import ContentType, TaskCreate, TaskType
from ltt.services.learning import (
    ContentNotFoundError,
    attach_content_to_task,
    create_content,
    get_content,
    get_relevant_content,
    get_task_content,
)
from ltt.services.learning.content import TaskNotFoundError
from ltt.services.task_service import create_task


@pytest.mark.asyncio
async def test_create_content(async_session):
    """Test creating content."""
    content = await create_content(
        async_session,
        ContentType.MARKDOWN,
        "# Python Basics\n\nLearn Python fundamentals.",
        metadata={"author": "instructor", "difficulty": "beginner"},
    )

    assert content.content_type == ContentType.MARKDOWN
    assert content.body == "# Python Basics\n\nLearn Python fundamentals."
    assert content.metadata == {"author": "instructor", "difficulty": "beginner"}
    assert content.id.startswith("cnt-")


@pytest.mark.asyncio
async def test_create_content_without_metadata(async_session):
    """Test creating content without metadata."""
    content = await create_content(async_session, ContentType.CODE, "print('Hello, World!')")

    assert content.content_type == ContentType.CODE
    assert content.body == "print('Hello, World!')"
    assert content.metadata == {}


@pytest.mark.asyncio
async def test_get_content(async_session):
    """Test getting content by ID."""
    created = await create_content(
        async_session, ContentType.EXTERNAL_LINK, "https://docs.python.org"
    )

    retrieved = await get_content(async_session, created.id)

    assert retrieved.id == created.id
    assert retrieved.content_type == ContentType.EXTERNAL_LINK
    assert retrieved.body == "https://docs.python.org"


@pytest.mark.asyncio
async def test_get_content_not_found(async_session):
    """Test getting nonexistent content."""
    with pytest.raises(ContentNotFoundError, match="does not exist"):
        await get_content(async_session, "nonexistent-content")


@pytest.mark.asyncio
async def test_attach_content_to_task(async_session):
    """Test attaching content to a task."""
    # Create project and task
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Learn Python",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
        ),
    )

    # Create content
    content = await create_content(async_session, ContentType.MARKDOWN, "Python tutorial content")

    # Attach content to task
    await attach_content_to_task(async_session, content.id, task.id)

    # Verify attachment
    task_content = await get_task_content(async_session, task.id)
    assert len(task_content) == 1
    assert task_content[0].id == content.id


@pytest.mark.asyncio
async def test_attach_multiple_content_to_task(async_session):
    """Test attaching multiple content items to a task."""
    # Create project and task
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Learn Python",
            task_type=TaskType.TASK,
            parent_id=project.id,
            project_id=project.id,
        ),
    )

    # Create multiple content items
    content1 = await create_content(async_session, ContentType.MARKDOWN, "Tutorial part 1")
    content2 = await create_content(async_session, ContentType.CODE, "example_code.py")
    content3 = await create_content(
        async_session, ContentType.VIDEO_REF, "https://youtube.com/watch?v=..."
    )

    # Attach all content
    await attach_content_to_task(async_session, content1.id, task.id)
    await attach_content_to_task(async_session, content2.id, task.id)
    await attach_content_to_task(async_session, content3.id, task.id)

    # Verify all attached
    task_content = await get_task_content(async_session, task.id)
    assert len(task_content) == 3
    content_ids = {c.id for c in task_content}
    assert content_ids == {content1.id, content2.id, content3.id}


@pytest.mark.asyncio
async def test_attach_content_idempotent(async_session):
    """Test that attaching same content twice doesn't duplicate."""
    # Create project, task and content
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )
    content = await create_content(async_session, ContentType.MARKDOWN, "Content")

    # Attach twice
    await attach_content_to_task(async_session, content.id, task.id)
    await attach_content_to_task(async_session, content.id, task.id)

    # Verify only one attachment
    task_content = await get_task_content(async_session, task.id)
    assert len(task_content) == 1


@pytest.mark.asyncio
async def test_attach_content_nonexistent_content(async_session):
    """Test attaching nonexistent content fails."""
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )

    with pytest.raises(ContentNotFoundError, match="does not exist"):
        await attach_content_to_task(async_session, "nonexistent-content", task.id)


@pytest.mark.asyncio
async def test_attach_content_nonexistent_task(async_session):
    """Test attaching content to nonexistent task fails."""
    content = await create_content(async_session, ContentType.MARKDOWN, "Content")

    with pytest.raises(TaskNotFoundError, match="does not exist"):
        await attach_content_to_task(async_session, content.id, "nonexistent-task")


@pytest.mark.asyncio
async def test_get_task_content_empty(async_session):
    """Test getting content for task with no content."""
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )

    task_content = await get_task_content(async_session, task.id)

    assert task_content == []


@pytest.mark.asyncio
async def test_get_relevant_content(async_session):
    """Test getting relevant content for a learner."""
    # Create project, task and content
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task", task_type=TaskType.TASK, parent_id=project.id, project_id=project.id
        ),
    )
    content = await create_content(async_session, ContentType.MARKDOWN, "Tutorial")

    # Attach content
    await attach_content_to_task(async_session, content.id, task.id)

    # Get relevant content (for MVP, same as get_task_content)
    learner_id = "test-learner"
    relevant = await get_relevant_content(async_session, task.id, learner_id)

    assert len(relevant) == 1
    assert relevant[0].id == content.id


@pytest.mark.asyncio
async def test_create_content_all_types(async_session):
    """Test creating content of all types."""
    # Test all content types
    markdown = await create_content(async_session, ContentType.MARKDOWN, "# Markdown content")
    code = await create_content(async_session, ContentType.CODE, "def hello(): pass")
    video = await create_content(async_session, ContentType.VIDEO_REF, "https://youtube.com/xyz")
    link = await create_content(async_session, ContentType.EXTERNAL_LINK, "https://example.com")

    assert markdown.content_type == ContentType.MARKDOWN
    assert code.content_type == ContentType.CODE
    assert video.content_type == ContentType.VIDEO_REF
    assert link.content_type == ContentType.EXTERNAL_LINK
