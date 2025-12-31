"""
Task Management Service for the Learning Task Tracker.

Handles CRUD operations for tasks, hierarchy traversal, and comments.
Based on PRD section 5.1.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ltt.models import (
    Comment,
    CommentCreate,
    CommentModel,
    Task,
    TaskCreate,
    TaskModel,
    TaskUpdate,
)
from ltt.utils.ids import PREFIX_COMMENT, generate_entity_id, generate_task_id


class TaskNotFoundError(Exception):
    """Raised when a task cannot be found."""

    pass


class InvalidTaskHierarchyError(Exception):
    """Raised when task hierarchy constraints are violated."""

    pass


async def create_task(session: AsyncSession, task_data: TaskCreate) -> Task:
    """
    Create a new task at any hierarchy level.

    Args:
        session: Database session
        task_data: Task creation data

    Returns:
        Created task

    Raises:
        InvalidTaskHierarchyError: If hierarchy constraints are violated
    """
    # Validate parent exists if specified
    if task_data.parent_id:
        parent = await session.get(TaskModel, task_data.parent_id)
        if not parent:
            raise InvalidTaskHierarchyError(f"Parent task {task_data.parent_id} does not exist")

        # Set project_id from parent if not provided
        if not task_data.project_id:
            task_data.project_id = parent.project_id

    # Generate ID if not provided
    if not task_data.id:
        if task_data.parent_id:
            # Get next child number
            result = await session.execute(
                select(TaskModel.id)
                .where(TaskModel.parent_id == task_data.parent_id)
                .order_by(TaskModel.id.desc())
            )
            existing_ids = [row[0] for row in result.all()]

            # Extract child numbers and find max
            max_child_num = 0
            for child_id in existing_ids:
                # ID format: parent_id.N
                parts = child_id.split(".")
                if len(parts) > 0:
                    try:
                        child_num = int(parts[-1])
                        max_child_num = max(max_child_num, child_num)
                    except ValueError:
                        continue

            task_id = generate_task_id(
                task_data.parent_id,
                task_data.project_id or "proj",
                lambda _: max_child_num + 1,
            )
        else:
            # Root task (project)
            task_id = generate_task_id(None, task_data.project_id or "proj", lambda _: 0)

            # If this is a project, set project_id to itself
            if task_data.task_type.value == "project":
                task_data.project_id = task_id
    else:
        task_id = task_data.id

    # Validate project_id is set
    if not task_data.project_id:
        raise InvalidTaskHierarchyError("project_id must be set for non-project tasks")

    # Create task model
    task_model = TaskModel(
        id=task_id,
        parent_id=task_data.parent_id,
        project_id=task_data.project_id,
        title=task_data.title,
        description=task_data.description,
        acceptance_criteria=task_data.acceptance_criteria,
        notes=task_data.notes,
        priority=task_data.priority,
        task_type=task_data.task_type.value,
        estimated_minutes=task_data.estimated_minutes,
        content=task_data.content,
        content_refs=task_data.content_refs or [],
        tutor_guidance=task_data.tutor_guidance,
        narrative_context=task_data.narrative_context,
    )

    session.add(task_model)
    await session.commit()
    await session.refresh(task_model)

    return Task.model_validate(task_model)


async def get_task(session: AsyncSession, task_id: str, load_relationships: bool = False) -> Task:
    """
    Retrieve a task by ID.

    Args:
        session: Database session
        task_id: Task ID
        load_relationships: Whether to eagerly load relationships

    Returns:
        Task

    Raises:
        TaskNotFoundError: If task does not exist
    """
    query = select(TaskModel).where(TaskModel.id == task_id)

    if load_relationships:
        query = query.options(
            selectinload(TaskModel.learning_objectives),
            selectinload(TaskModel.acceptance_criteria_list),
            selectinload(TaskModel.comments),
        )

    result = await session.execute(query)
    task_model = result.scalar_one_or_none()

    if not task_model:
        raise TaskNotFoundError(f"Task {task_id} not found")

    return Task.model_validate(task_model)


async def update_task(session: AsyncSession, task_id: str, updates: TaskUpdate) -> Task:
    """
    Update an existing task.

    Args:
        session: Database session
        task_id: Task ID
        updates: Fields to update

    Returns:
        Updated task

    Raises:
        TaskNotFoundError: If task does not exist
    """
    task_model = await session.get(TaskModel, task_id)
    if not task_model:
        raise TaskNotFoundError(f"Task {task_id} not found")

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task_model, field, value)

    task_model.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(task_model)

    return Task.model_validate(task_model)


async def delete_task(session: AsyncSession, task_id: str) -> None:
    """
    Delete a task and all its children (cascade).

    Args:
        session: Database session
        task_id: Task ID

    Raises:
        TaskNotFoundError: If task does not exist
    """
    task_model = await session.get(TaskModel, task_id)
    if not task_model:
        raise TaskNotFoundError(f"Task {task_id} not found")

    await session.delete(task_model)
    await session.commit()


async def get_children(session: AsyncSession, task_id: str, recursive: bool = False) -> list[Task]:
    """
    Get direct children of a task, optionally recursive.

    Args:
        session: Database session
        task_id: Parent task ID
        recursive: Whether to get all descendants

    Returns:
        List of child tasks
    """
    if not recursive:
        # Direct children only
        result = await session.execute(select(TaskModel).where(TaskModel.parent_id == task_id))
        children = result.scalars().all()
        return [Task.model_validate(child) for child in children]

    # Recursive: get all descendants
    # Use a CTE for recursive query
    descendants = []
    to_visit = [task_id]

    while to_visit:
        current_id = to_visit.pop(0)
        result = await session.execute(select(TaskModel).where(TaskModel.parent_id == current_id))
        children = result.scalars().all()

        for child in children:
            descendants.append(Task.model_validate(child))
            to_visit.append(child.id)

    return descendants


async def get_ancestors(session: AsyncSession, task_id: str) -> list[Task]:
    """
    Get all ancestors of a task (parent, grandparent, ..., project).

    Args:
        session: Database session
        task_id: Task ID

    Returns:
        List of ancestor tasks from nearest to farthest (parent first, project last)
    """
    ancestors = []
    current_id = task_id

    while True:
        task_model = await session.get(TaskModel, current_id)
        if not task_model or not task_model.parent_id:
            break

        parent_model = await session.get(TaskModel, task_model.parent_id)
        if not parent_model:
            break

        ancestors.append(Task.model_validate(parent_model))
        current_id = parent_model.id

    return ancestors


async def add_comment(
    session: AsyncSession,
    task_id: str,
    comment_data: CommentCreate,
) -> Comment:
    """
    Add a comment to a task.

    Args:
        session: Database session
        task_id: Task ID
        comment_data: Comment data

    Returns:
        Created comment

    Raises:
        TaskNotFoundError: If task does not exist
    """
    # Verify task exists
    task_model = await session.get(TaskModel, task_id)
    if not task_model:
        raise TaskNotFoundError(f"Task {task_id} not found")

    comment_model = CommentModel(
        id=generate_entity_id(PREFIX_COMMENT),
        task_id=task_id,
        learner_id=comment_data.learner_id,
        author=comment_data.author,
        text=comment_data.text,
    )

    session.add(comment_model)
    await session.commit()
    await session.refresh(comment_model)

    return Comment.model_validate(comment_model)


async def get_comments(
    session: AsyncSession, task_id: str, learner_id: str | None = None
) -> list[Comment]:
    """
    Get comments for a task.

    Args:
        session: Database session
        task_id: Task ID
        learner_id: If provided, include private comments for this learner

    Returns:
        List of comments (shared + private if learner_id provided)
    """
    query = select(CommentModel).where(CommentModel.task_id == task_id)

    if learner_id:
        # Get shared comments (learner_id IS NULL) OR private comments for this learner
        query = query.where(
            (CommentModel.learner_id.is_(None)) | (CommentModel.learner_id == learner_id)
        )
    else:
        # Only shared comments
        query = query.where(CommentModel.learner_id.is_(None))

    result = await session.execute(query.order_by(CommentModel.created_at))
    comments = result.scalars().all()

    return [Comment.model_validate(comment) for comment in comments]


async def get_task_count(session: AsyncSession, project_id: str | None = None) -> int:
    """
    Get total count of tasks, optionally filtered by project.

    Args:
        session: Database session
        project_id: Optional project ID filter

    Returns:
        Task count
    """
    query = select(func.count(TaskModel.id))

    if project_id:
        query = query.where(TaskModel.project_id == project_id)

    result = await session.execute(query)
    return result.scalar() or 0
