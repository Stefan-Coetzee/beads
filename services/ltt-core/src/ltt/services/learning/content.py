"""
Content management service.

Manages learning content that can be attached to tasks.
"""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import Content, ContentModel, ContentType, TaskModel
from ltt.utils.ids import PREFIX_CONTENT, generate_entity_id

# ============================================================================
# Exceptions
# ============================================================================


class ContentError(Exception):
    """Base exception for content operations."""


class ContentNotFoundError(ContentError):
    """Content does not exist."""


class TaskNotFoundError(ContentError):
    """Referenced task does not exist."""


# ============================================================================
# Content Operations
# ============================================================================


async def create_content(
    session: AsyncSession,
    content_type: ContentType,
    body: str,
    metadata: dict | None = None,
) -> Content:
    """
    Create a content item.

    Args:
        session: Database session
        content_type: Type of content
        body: Content body
        metadata: Optional metadata

    Returns:
        Created content
    """
    content_id = generate_entity_id(PREFIX_CONTENT)
    content = ContentModel(
        id=content_id,
        content_type=content_type.value,
        body=body,
        content_metadata=json.dumps(metadata or {}),
    )
    session.add(content)

    await session.commit()
    await session.refresh(content)

    return Content(
        id=content.id,
        content_type=ContentType(content.content_type),
        body=content.body,
        metadata=json.loads(content.content_metadata) if content.content_metadata else {},
        created_at=content.created_at,
    )


async def get_content(
    session: AsyncSession,
    content_id: str,
) -> Content:
    """
    Get content by ID.

    Args:
        session: Database session
        content_id: Content ID

    Returns:
        Content

    Raises:
        ContentNotFoundError: If content doesn't exist
    """
    result = await session.execute(select(ContentModel).where(ContentModel.id == content_id))
    content = result.scalar_one_or_none()

    if not content:
        raise ContentNotFoundError(f"Content {content_id} does not exist")

    return Content(
        id=content.id,
        content_type=ContentType(content.content_type),
        body=content.body,
        metadata=json.loads(content.content_metadata) if content.content_metadata else {},
        created_at=content.created_at,
    )


async def attach_content_to_task(
    session: AsyncSession,
    content_id: str,
    task_id: str,
) -> None:
    """
    Attach content to a task.

    Adds content_id to task's content_refs array.

    Args:
        session: Database session
        content_id: Content ID to attach
        task_id: Task ID to attach to

    Raises:
        ContentNotFoundError: If content doesn't exist
        TaskNotFoundError: If task doesn't exist
    """
    # Verify content exists
    content_result = await session.execute(
        select(ContentModel).where(ContentModel.id == content_id)
    )
    content = content_result.scalar_one_or_none()

    if not content:
        raise ContentNotFoundError(f"Content {content_id} does not exist")

    # Verify task exists and get it
    task_result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = task_result.scalar_one_or_none()

    if not task:
        raise TaskNotFoundError(f"Task {task_id} does not exist")

    # Add content_id to task's content_refs if not already there
    # content_refs is a PostgreSQL ARRAY, already a list
    content_refs = list(task.content_refs) if task.content_refs else []
    if content_id not in content_refs:
        content_refs.append(content_id)
        task.content_refs = content_refs

        await session.commit()


async def get_task_content(
    session: AsyncSession,
    task_id: str,
) -> list[Content]:
    """
    Get all content for a task.

    Returns both inline content and referenced content.

    Args:
        session: Database session
        task_id: Task ID

    Returns:
        List of content items
    """
    # Verify task exists and get content_refs
    task_result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = task_result.scalar_one_or_none()

    if not task:
        raise TaskNotFoundError(f"Task {task_id} does not exist")

    # Get content IDs (content_refs is a PostgreSQL ARRAY, already a list)
    content_ids = task.content_refs if task.content_refs else []

    if not content_ids:
        return []

    # Fetch all content items
    result = await session.execute(select(ContentModel).where(ContentModel.id.in_(content_ids)))
    content_items = result.scalars().all()

    return [
        Content(
            id=c.id,
            content_type=ContentType(c.content_type),
            body=c.body,
            metadata=json.loads(c.content_metadata) if c.content_metadata else {},
            created_at=c.created_at,
        )
        for c in content_items
    ]


async def get_relevant_content(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
) -> list[Content]:
    """
    Get content relevant for a learner on a task.

    For MVP, this is the same as get_task_content.
    Future: personalize based on learner's skill gaps.

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID (for future personalization)

    Returns:
        List of relevant content items
    """
    # For now, just return all task content
    # Future enhancement: filter/reorder based on learner's progress and needs
    return await get_task_content(session, task_id)
