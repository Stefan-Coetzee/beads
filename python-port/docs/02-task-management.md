# Task Management Module

> CRUD operations, hierarchy management, and status transitions for tasks.

> **IMPORTANT: Two-Layer Architecture (ADR-001)**
>
> This module implements the two-layer architecture defined in [ADR-001](./adr/001-learner-scoped-task-progress.md):
>
> - **Template Layer (`tasks` table)**: Shared task definitions (title, description, hierarchy)
> - **Instance Layer (`learner_task_progress` table)**: Per-learner status tracking
>
> **Key principle**: Task status is per-learner. When Learner A closes a task, it remains open for Learner B.
>
> All status operations require `learner_id` and operate on the `learner_task_progress` table, NOT the `tasks` table.

## Overview

This module handles the core task lifecycle:
- Creating tasks at any hierarchy level (template layer)
- Updating task fields (template layer)
- Managing status transitions with validation rules (instance layer, per-learner)
- Traversing the task hierarchy (template layer)
- Attaching comments and feedback (dual-purpose: shared or per-learner)

### Reference: Beads Implementation

Key files to reference:
- [internal/storage/sqlite/issues.go](../internal/storage/sqlite/issues.go) - CRUD operations
- [internal/storage/sqlite/validators.go](../internal/storage/sqlite/validators.go) - Status validation
- [internal/storage/sqlite/ids.go](../internal/storage/sqlite/ids.go) - ID generation
- [ADR-001: Two-Layer Architecture](./adr/001-learner-scoped-task-progress.md) - **Authoritative architecture reference**
---

## 1. Service Interface

```python
from typing import List, Optional
from datetime import datetime

from ltt.models import (
    Task, TaskCreate, TaskUpdate, TaskDetail, TaskSummary,
    TaskStatus, TaskType,
    Comment, CommentCreate,
    Event, EventType
)


class TaskService:
    """
    Service for task management operations.

    All methods are async and interact with the database.
    Events are recorded for audit trail.
    """

    def __init__(self, db_session, event_service: "EventService"):
        self.db = db_session
        self.events = event_service

    # ─────────────────────────────────────────────────────────────
    # CRUD Operations
    # ─────────────────────────────────────────────────────────────

    async def create_task(
        self,
        task: TaskCreate,
        actor: str
    ) -> Task:
        """
        Create a new task at any hierarchy level.

        Args:
            task: Task creation data
            actor: ID of creator (learner_id or 'system')

        Returns:
            Created task with generated ID

        Raises:
            ValueError: If parent_id doesn't exist
            ValueError: If project_id missing for non-project tasks
        """
        ...

    async def get_task(
        self,
        task_id: str,
        include_children: bool = False
    ) -> Task:
        """
        Get a task by ID.

        Args:
            task_id: Task identifier
            include_children: Whether to load child tasks

        Returns:
            Task entity

        Raises:
            NotFoundError: If task doesn't exist
        """
        ...

    async def get_task_detail(
        self,
        task_id: str
    ) -> TaskDetail:
        """
        Get task with all related data for detailed view.

        Includes:
        - Learning objectives
        - Children
        - Comments
        - Dependencies (blocked_by, blocks)

        Args:
            task_id: Task identifier

        Returns:
            TaskDetail with all relationships loaded
        """
        ...

    async def update_task(
        self,
        task_id: str,
        updates: TaskUpdate,
        actor: str
    ) -> Task:
        """
        Update task fields.

        Args:
            task_id: Task identifier
            updates: Fields to update (only non-None values applied)
            actor: ID of updater

        Returns:
            Updated task

        Raises:
            NotFoundError: If task doesn't exist
        """
        ...

    async def delete_task(
        self,
        task_id: str,
        actor: str,
        cascade: bool = True
    ) -> None:
        """
        Delete a task.

        Args:
            task_id: Task identifier
            actor: ID of deleter
            cascade: If True, delete children. If False, fail if has children.

        Raises:
            NotFoundError: If task doesn't exist
            ValueError: If cascade=False and task has children
        """
        ...

    # ─────────────────────────────────────────────────────────────
    # Status Management (Instance Layer - Per-Learner)
    # ─────────────────────────────────────────────────────────────

    async def get_or_create_progress(
        self,
        task_id: str,
        learner_id: str
    ) -> LearnerTaskProgress:
        """
        Get or create progress record for a learner on a task.

        This implements lazy initialization - progress records are created
        on first access, not pre-populated for all learners.

        Args:
            task_id: Task identifier
            learner_id: Learner identifier

        Returns:
            LearnerTaskProgress record (existing or newly created with status='open')

        Raises:
            NotFoundError: If task doesn't exist
        """
        ...

    async def update_status(
        self,
        task_id: str,
        learner_id: str,
        new_status: TaskStatus,
        actor: str,
        reason: Optional[str] = None
    ) -> LearnerTaskProgress:
        """
        Update task status for a specific learner.

        IMPORTANT: This operates on the learner_task_progress table, NOT the tasks table.
        Status is per-learner - updating one learner's status does not affect others.

        Validates:
        - Transition is allowed (see VALID_TRANSITIONS)
        - For closing: all children are closed (for this learner)
        - For closing subtasks: has passing validation (for this learner)

        Args:
            task_id: Task identifier
            learner_id: Learner whose status is being updated
            new_status: Target status
            actor: ID of actor (typically same as learner_id)
            reason: Optional reason (required for closing)

        Returns:
            Updated learner_task_progress record

        Raises:
            NotFoundError: If task doesn't exist
            StatusTransitionError: If transition not allowed
            ValidationRequiredError: If subtask needs validation to close
        """
        ...

    async def reopen_task(
        self,
        task_id: str,
        learner_id: str,
        actor: str,
        reason: Optional[str] = None
    ) -> LearnerTaskProgress:
        """
        Reopen a closed task for a specific learner (go_back functionality).

        This is a special status transition from closed -> open.
        Only affects this learner's progress - other learners are unaffected.

        Args:
            task_id: Task identifier
            learner_id: Learner whose progress is being reopened
            actor: ID of actor (typically same as learner_id)
            reason: Why the task is being reopened

        Returns:
            Reopened learner_task_progress record
        """
        ...

    async def can_close_task(
        self,
        task_id: str,
        learner_id: str
    ) -> tuple[bool, str]:
        """
        Check if a task can be closed for a specific learner.

        Checks (for this learner):
        - All children are closed
        - For subtasks: has passing validation

        Args:
            task_id: Task identifier
            learner_id: Learner attempting to close

        Returns:
            (can_close, reason) - reason explains why if can_close is False
        """
        ...

    # ─────────────────────────────────────────────────────────────
    # Hierarchy Operations
    # ─────────────────────────────────────────────────────────────

    async def get_children(
        self,
        task_id: str,
        learner_id: Optional[str] = None,
        recursive: bool = False,
        status: Optional[TaskStatus] = None
    ) -> List[Task]:
        """
        Get child tasks (optionally with learner-specific status).

        Args:
            task_id: Parent task ID
            learner_id: If provided, joins with learner_task_progress to include status
            recursive: If True, get all descendants
            status: Filter by status (requires learner_id)

        Returns:
            List of child tasks (with learner_status field if learner_id provided)

        Note:
            When learner_id is provided, returned tasks include a learner_status field
            showing this learner's progress. Status filtering only works with learner_id.
        """
        ...

    async def get_ancestors(
        self,
        task_id: str
    ) -> List[Task]:
        """
        Get ancestor chain from task up to project root.

        Returns list ordered from immediate parent to project:
        [parent, grandparent, ..., epic, project]

        Args:
            task_id: Task identifier

        Returns:
            List of ancestors, empty if task is a project
        """
        ...

    async def get_siblings(
        self,
        task_id: str
    ) -> List[Task]:
        """
        Get sibling tasks (same parent).

        Args:
            task_id: Task identifier

        Returns:
            List of siblings (excluding self)
        """
        ...

    async def move_task(
        self,
        task_id: str,
        new_parent_id: Optional[str],
        actor: str
    ) -> Task:
        """
        Move a task to a different parent.

        Regenerates ID to maintain hierarchy.
        Updates all child IDs recursively.

        Args:
            task_id: Task to move
            new_parent_id: New parent (None to make root)
            actor: ID of actor

        Returns:
            Task with new ID

        Raises:
            ValueError: If would create circular hierarchy
        """
        ...

    # ─────────────────────────────────────────────────────────────
    # Comments (Dual-Purpose: Shared or Per-Learner)
    # ─────────────────────────────────────────────────────────────

    async def add_comment(
        self,
        task_id: str,
        comment: CommentCreate,
        actor: str,
        learner_id: Optional[str] = None
    ) -> Comment:
        """
        Add a comment to a task.

        Comments can be shared (visible to all) or private to a specific learner:
        - learner_id=None: Shared comment (instructor notes, general guidance)
        - learner_id=set: Private to that learner (AI tutor conversation)

        Args:
            task_id: Task identifier
            comment: Comment data
            actor: ID of commenter
            learner_id: If set, comment is private to this learner. If None, shared.

        Returns:
            Created comment
        """
        ...

    async def get_comments(
        self,
        task_id: str,
        learner_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Comment]:
        """
        Get comments on a task visible to a learner.

        Returns:
        - All shared comments (learner_id=NULL)
        - Plus learner's private comments (if learner_id provided)

        Args:
            task_id: Task identifier
            learner_id: If provided, includes learner's private comments
            limit: Maximum comments to return

        Returns:
            List of comments, newest first
        """
        ...

    # ─────────────────────────────────────────────────────────────
    # Query Operations
    # ─────────────────────────────────────────────────────────────

    async def list_tasks(
        self,
        project_id: str,
        learner_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        parent_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Task]:
        """
        List tasks with filtering (optionally with learner-specific status).

        Args:
            project_id: Filter by project
            learner_id: If provided, joins with learner_task_progress to include status
            status: Filter by status (requires learner_id)
            task_type: Filter by type
            parent_id: Filter by parent (direct children only)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of matching tasks (with learner_status field if learner_id provided)

        Note:
            Status filtering requires learner_id since status is per-learner.
        """
        ...

    async def search_tasks(
        self,
        project_id: str,
        query: str,
        limit: int = 20
    ) -> List[TaskSummary]:
        """
        Search tasks by title/description.

        Args:
            project_id: Scope to project
            query: Search string
            limit: Maximum results

        Returns:
            List of matching task summaries
        """
        ...
```

---

## 2. Status Transition Rules

### Valid Transitions

```python
from enum import Enum
from typing import Dict, Set

class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    CLOSED = "closed"


# Which transitions are allowed
VALID_TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
    TaskStatus.OPEN: {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED},
    TaskStatus.IN_PROGRESS: {TaskStatus.OPEN, TaskStatus.BLOCKED, TaskStatus.CLOSED},
    TaskStatus.BLOCKED: {TaskStatus.OPEN, TaskStatus.IN_PROGRESS},
    TaskStatus.CLOSED: {TaskStatus.OPEN},  # Only via explicit reopen
}
```

### Transition Logic

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class StatusTransitionResult:
    allowed: bool
    reason: Optional[str] = None


async def validate_status_transition(
    db,
    task: Task,
    current_status: TaskStatus,
    new_status: TaskStatus,
    learner_id: str
) -> StatusTransitionResult:
    """
    Validate if a status transition is allowed for a specific learner.

    IMPORTANT: This validates transitions on learner_task_progress, not tasks.
    The task parameter is the task template, current_status comes from learner_task_progress.

    Checks:
    1. Transition is in VALID_TRANSITIONS
    2. Additional rules for specific transitions (scoped to this learner)
    """

    # Check basic transition validity
    if new_status not in VALID_TRANSITIONS[current_status]:
        return StatusTransitionResult(
            allowed=False,
            reason=f"Cannot transition from '{current_status}' to '{new_status}'"
        )

    # Additional checks for closing
    if new_status == TaskStatus.CLOSED:
        # Check 1: All children must be closed (for this learner)
        # Query: Join task children with this learner's progress
        open_children = await get_children_with_learner_status(
            db, task.id, learner_id, exclude_status=TaskStatus.CLOSED
        )
        if open_children:
            child_ids = [c.id for c in open_children[:3]]
            return StatusTransitionResult(
                allowed=False,
                reason=f"Cannot close: {len(open_children)} children still open for you. "
                       f"Examples: {', '.join(child_ids)}"
            )

        # Check 2: Subtasks require passing validation (for this learner)
        if task.task_type == TaskType.SUBTASK:
            from ltt.services.validation import get_latest_validation
            validation = await get_latest_validation(db, task.id, learner_id)

            if validation is None:
                return StatusTransitionResult(
                    allowed=False,
                    reason="Subtask requires a submission and validation before closing"
                )

            if not validation.passed:
                return StatusTransitionResult(
                    allowed=False,
                    reason=f"Subtask validation failed: {validation.error_message}"
                )

    return StatusTransitionResult(allowed=True)
```

### Automatic Status Updates

Certain operations trigger automatic status updates (per-learner):

```python
async def handle_child_status_change(
    db,
    parent_id: str,
    learner_id: str,
    actor: str
) -> None:
    """
    Update parent status when child status changes for a specific learner.

    IMPORTANT: Only affects this learner's progress on the parent task.

    Rules (per-learner):
    - If parent was closed and child reopened -> reopen parent for this learner
    - If all children closed -> parent can now be closed (but isn't auto-closed)
    """
    # Get parent's progress for this learner
    parent_progress = await get_or_create_progress(db, parent_id, learner_id)

    if parent_progress.status == TaskStatus.CLOSED:
        # Parent was closed, child reopened -> reopen parent for this learner
        await update_status(db, parent_id, learner_id, TaskStatus.OPEN, actor,
                          reason="Child task reopened")
        return

    # Check if any children are blocking (for this learner)
    open_children = await get_children_with_learner_status(
        db, parent_id, learner_id, exclude_status=TaskStatus.CLOSED
    )

    if open_children and parent_progress.status == TaskStatus.CLOSED:
        # Shouldn't happen, but handle gracefully
        await update_status(db, parent_id, learner_id, TaskStatus.IN_PROGRESS, actor,
                          reason="Children still open")
```

---

## 3. Learner Progress Management

### Get or Create Progress (Lazy Initialization)

```python
async def get_or_create_progress(
    db,
    task_id: str,
    learner_id: str
) -> LearnerTaskProgress:
    """
    Get or create progress record for a learner on a task.

    This implements lazy initialization per ADR-001:
    - Progress records are NOT pre-created for all learners
    - They are created on first access (view, status update, etc.)
    - Default status is 'open'

    Args:
        db: Database session
        task_id: Task identifier
        learner_id: Learner identifier

    Returns:
        Existing or newly created progress record

    Raises:
        NotFoundError: If task doesn't exist
    """
    from ltt.models import LearnerTaskProgressModel
    from sqlalchemy import select

    # Check if progress already exists
    result = await db.execute(
        select(LearnerTaskProgressModel)
        .where(
            LearnerTaskProgressModel.task_id == task_id,
            LearnerTaskProgressModel.learner_id == learner_id
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        return LearnerTaskProgress.model_validate(existing)

    # Verify task exists
    task = await db.get(TaskModel, task_id)
    if not task:
        raise NotFoundError(task_id)

    # Create new progress record with default status
    new_progress = LearnerTaskProgressModel(
        id=generate_entity_id("ltp"),
        task_id=task_id,
        learner_id=learner_id,
        status=TaskStatus.OPEN.value,
        started_at=None,
        completed_at=None
    )
    db.add(new_progress)
    await db.flush()

    return LearnerTaskProgress.model_validate(new_progress)
```

### Update Status (Instance Layer)

```python
async def update_status(
    db,
    task_id: str,
    learner_id: str,
    new_status: TaskStatus,
    actor: str,
    event_service: EventService,
    reason: Optional[str] = None
) -> LearnerTaskProgress:
    """
    Update task status for a specific learner.

    IMPORTANT: Operates on learner_task_progress table, NOT tasks table.
    """
    from datetime import datetime, timezone

    # Get or create progress record
    progress = await get_or_create_progress(db, task_id, learner_id)

    # Get task template for validation
    task = await db.get(TaskModel, task_id)
    if not task:
        raise NotFoundError(task_id)

    # Validate transition
    validation = await validate_status_transition(
        db, task, progress.status, new_status, learner_id
    )
    if not validation.allowed:
        raise StatusTransitionError(
            task_id, progress.status, new_status, validation.reason
        )

    # Update status in learner_task_progress table
    old_status = progress.status
    progress_model = await db.get(LearnerTaskProgressModel, progress.id)

    progress_model.status = new_status.value

    # Update timestamps
    if new_status == TaskStatus.IN_PROGRESS and not progress_model.started_at:
        progress_model.started_at = datetime.now(timezone.utc)
    elif new_status == TaskStatus.CLOSED:
        progress_model.completed_at = datetime.now(timezone.utc)
    elif new_status == TaskStatus.OPEN and old_status == TaskStatus.CLOSED:
        # Reopening - clear completion timestamp
        progress_model.completed_at = None

    await db.flush()

    # Record event
    await event_service.record(
        entity_type="learner_task_progress",
        entity_id=progress.id,
        event_type=EventType.STATUS_CHANGED,
        actor=actor,
        old_value=old_status,
        new_value=new_status.value
    )

    await db.commit()
    return LearnerTaskProgress.model_validate(progress_model)
```

---

## 4. Task Creation Flow

```python
async def create_task(
    db,
    task: TaskCreate,
    actor: str,
    event_service: EventService
) -> Task:
    """
    Create a new task with all validations.
    """

    # 1. Validate parent exists (if specified)
    parent = None
    if task.parent_id:
        parent = await db.get(TaskModel, task.parent_id)
        if not parent:
            raise ValueError(f"Parent task '{task.parent_id}' not found")

    # 2. Determine project_id
    if task.task_type == TaskType.PROJECT:
        # Projects are their own project
        project_id = None  # Will be set to own ID after generation
    elif task.project_id:
        project_id = task.project_id
    elif parent:
        project_id = parent.project_id
    else:
        raise ValueError("project_id required for non-project tasks without parent")

    # 3. Generate ID
    if task.id:
        # Custom ID provided - validate format
        generated_id = task.id
    else:
        # Generate hierarchical ID
        prefix = project_id.split("-")[0] if project_id else "proj"
        generated_id = await generate_task_id(
            db,
            parent_id=task.parent_id,
            project_prefix=prefix
        )

    # 4. For projects, set project_id to self
    if task.task_type == TaskType.PROJECT:
        project_id = generated_id

    # 5. Create the task (template layer - no status)
    db_task = TaskModel(
        id=generated_id,
        parent_id=task.parent_id,
        project_id=project_id,
        title=task.title,
        description=task.description,
        acceptance_criteria=task.acceptance_criteria,
        notes=task.notes,
        priority=task.priority,
        task_type=task.task_type.value,
        estimated_minutes=task.estimated_minutes,
        content=task.content,
        content_refs=task.content_refs,
        # NO status field - that's in learner_task_progress
    )

    db.add(db_task)
    await db.flush()

    # 6. Create implicit parent-child dependency
    if task.parent_id:
        from ltt.services.dependency import add_dependency
        await add_dependency(
            db,
            task_id=generated_id,
            depends_on_id=task.parent_id,
            dependency_type=DependencyType.PARENT_CHILD,
            actor=actor
        )

    # 7. Record event
    await event_service.record(
        entity_type="task",
        entity_id=generated_id,
        event_type=EventType.CREATED,
        actor=actor,
        new_value=generated_id
    )

    await db.commit()
    return Task.model_validate(db_task)
```

---

## 4. Hierarchical ID Generation

Following beads pattern from [internal/storage/sqlite/ids.go](../internal/storage/sqlite/ids.go):

```python
import hashlib
from uuid import uuid4
from typing import Optional, Callable, Awaitable


async def generate_task_id(
    db,
    parent_id: Optional[str],
    project_prefix: str
) -> str:
    """
    Generate a hierarchical task ID.

    Root tasks (no parent):
        {prefix}-{4-char-hash}
        Example: "proj-a1b2"

    Child tasks:
        {parent_id}.{counter}
        Example: "proj-a1b2.1", "proj-a1b2.1.1"
    """
    if parent_id is None:
        # Root task: generate hash-based ID
        unique_bytes = uuid4().bytes
        hash_digest = hashlib.sha256(unique_bytes).hexdigest()[:4]
        return f"{project_prefix}-{hash_digest}"
    else:
        # Child task: get next counter for this parent
        next_number = await get_next_child_number(db, parent_id)
        return f"{parent_id}.{next_number}"


async def get_next_child_number(db, parent_id: str) -> int:
    """
    Get and increment the child counter for a parent.

    Uses a separate counters table to avoid race conditions.
    """
    # Try to get existing counter
    result = await db.execute(
        select(ChildCounterModel).where(ChildCounterModel.parent_id == parent_id)
    )
    counter = result.scalar_one_or_none()

    if counter:
        counter.last_child += 1
        next_number = counter.last_child
    else:
        # First child - also check existing children for recovery
        result = await db.execute(
            select(func.count()).where(TaskModel.parent_id == parent_id)
        )
        existing_count = result.scalar() or 0

        next_number = existing_count + 1
        counter = ChildCounterModel(parent_id=parent_id, last_child=next_number)
        db.add(counter)

    await db.flush()
    return next_number
```

---

## 5. Hierarchy Traversal

### Get Ancestors (Path to Root)

```python
async def get_ancestors(db, task_id: str) -> List[Task]:
    """
    Get the ancestor chain from task up to project root.

    Uses recursive CTE for efficient single-query traversal.
    """
    # PostgreSQL recursive CTE
    ancestors_cte = """
    WITH RECURSIVE ancestors AS (
        -- Base case: start with the task's parent
        SELECT t.*, 1 as depth
        FROM tasks t
        WHERE t.id = (SELECT parent_id FROM tasks WHERE id = :task_id)

        UNION ALL

        -- Recursive case: get each parent's parent
        SELECT t.*, a.depth + 1
        FROM tasks t
        JOIN ancestors a ON t.id = a.parent_id
        WHERE a.depth < 50  -- Safety limit
    )
    SELECT * FROM ancestors ORDER BY depth ASC
    """

    result = await db.execute(text(ancestors_cte), {"task_id": task_id})
    rows = result.fetchall()
    return [Task.model_validate(row) for row in rows]
```

### Get Descendants (All Children)

```python
async def get_descendants(
    db,
    task_id: str,
    max_depth: int = 50
) -> List[Task]:
    """
    Get all descendants of a task recursively.
    """
    descendants_cte = """
    WITH RECURSIVE descendants AS (
        -- Base case: direct children
        SELECT t.*, 1 as depth
        FROM tasks t
        WHERE t.parent_id = :task_id

        UNION ALL

        -- Recursive case: children of children
        SELECT t.*, d.depth + 1
        FROM tasks t
        JOIN descendants d ON t.parent_id = d.id
        WHERE d.depth < :max_depth
    )
    SELECT * FROM descendants ORDER BY depth ASC, id ASC
    """

    result = await db.execute(
        text(descendants_cte),
        {"task_id": task_id, "max_depth": max_depth}
    )
    rows = result.fetchall()
    return [Task.model_validate(row) for row in rows]
```

---

## 6. Error Types

```python
class TaskError(Exception):
    """Base exception for task operations."""
    pass


class NotFoundError(TaskError):
    """Task not found."""
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Task '{task_id}' not found")


class StatusTransitionError(TaskError):
    """Invalid status transition."""
    def __init__(self, task_id: str, from_status: str, to_status: str, reason: str):
        self.task_id = task_id
        self.from_status = from_status
        self.to_status = to_status
        self.reason = reason
        super().__init__(
            f"Cannot transition task '{task_id}' from '{from_status}' to '{to_status}': {reason}"
        )


class ValidationRequiredError(TaskError):
    """Task requires passing validation to close."""
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Task '{task_id}' requires passing validation before closing")


class HierarchyError(TaskError):
    """Invalid hierarchy operation."""
    pass
```

---

## 7. Event Recording

All mutations record events for audit trail:

```python
class EventService:
    """Records audit events for all operations."""

    def __init__(self, db):
        self.db = db

    async def record(
        self,
        entity_type: str,
        entity_id: str,
        event_type: EventType,
        actor: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None
    ) -> Event:
        """Record an audit event."""
        event = EventModel(
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type.value,
            actor=actor,
            old_value=old_value,
            new_value=new_value
        )
        self.db.add(event)
        await self.db.flush()
        return Event.model_validate(event)

    async def get_events(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50
    ) -> List[Event]:
        """Get events for an entity."""
        result = await self.db.execute(
            select(EventModel)
            .where(EventModel.entity_type == entity_type)
            .where(EventModel.entity_id == entity_id)
            .order_by(EventModel.created_at.desc())
            .limit(limit)
        )
        return [Event.model_validate(e) for e in result.scalars().all()]
```

---

## 8. Database Queries Reference

### Get Task with Learner Status

```sql
-- Get task template with this learner's status
SELECT
    t.*,
    COALESCE(ltp.status, 'open') as learner_status,
    ltp.started_at as learner_started_at,
    ltp.completed_at as learner_completed_at
FROM tasks t
LEFT JOIN learner_task_progress ltp
    ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
WHERE t.id = :task_id
```

### Get Task with Children Count (for a Learner)

```sql
-- Count children and their status for this learner
SELECT
    t.*,
    COALESCE(ltp.status, 'open') as learner_status,
    (SELECT COUNT(*) FROM tasks WHERE parent_id = t.id) as total_children,
    (SELECT COUNT(*)
     FROM tasks ct
     LEFT JOIN learner_task_progress cltp
         ON cltp.task_id = ct.id AND cltp.learner_id = :learner_id
     WHERE ct.parent_id = t.id
       AND COALESCE(cltp.status, 'open') = 'closed') as closed_children
FROM tasks t
LEFT JOIN learner_task_progress ltp
    ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
WHERE t.id = :task_id
```

### List Tasks with Progress (for a Learner)

```sql
-- List top-level tasks with this learner's progress
SELECT
    t.*,
    COALESCE(ltp.status, 'open') as learner_status,
    (SELECT COUNT(*) FROM tasks WHERE parent_id = t.id) as total_children,
    (SELECT COUNT(*)
     FROM tasks ct
     LEFT JOIN learner_task_progress cltp
         ON cltp.task_id = ct.id AND cltp.learner_id = :learner_id
     WHERE ct.parent_id = t.id
       AND COALESCE(cltp.status, 'open') = 'closed') as closed_children
FROM tasks t
LEFT JOIN learner_task_progress ltp
    ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
WHERE t.project_id = :project_id
    AND t.parent_id IS NULL  -- Top-level only
ORDER BY
    CASE COALESCE(ltp.status, 'open')
        WHEN 'in_progress' THEN 0
        WHEN 'open' THEN 1
        WHEN 'blocked' THEN 2
        WHEN 'closed' THEN 3
    END,
    t.priority ASC,
    t.created_at ASC
```

### Search Tasks

```sql
SELECT t.*
FROM tasks t
WHERE t.project_id = :project_id
    AND (
        t.title ILIKE '%' || :query || '%'
        OR t.description ILIKE '%' || :query || '%'
    )
ORDER BY
    CASE WHEN t.title ILIKE :query || '%' THEN 0 ELSE 1 END,
    t.created_at DESC
LIMIT :limit
```

### Get Comments (Shared + Per-Learner)

```sql
-- Get comments visible to this learner
-- Returns: shared comments (learner_id IS NULL) + learner's private comments
SELECT c.*
FROM comments c
WHERE c.task_id = :task_id
  AND (c.learner_id IS NULL OR c.learner_id = :learner_id)
ORDER BY c.created_at DESC
LIMIT :limit
```

---

## 9. File Structure

```
src/ltt/services/
├── __init__.py
├── task.py          # TaskService class
├── event.py         # EventService class
├── exceptions.py    # TaskError, NotFoundError, etc.
└── utils/
    └── ids.py       # ID generation utilities
```

---

## 10. Testing Requirements

Each function needs tests for:

1. **Happy Path**
   - Create task successfully
   - Update task fields
   - Status transitions that are allowed

2. **Validation Errors**
   - Invalid status transitions
   - Missing required fields
   - Subtask close without validation

3. **Hierarchy**
   - Create child tasks
   - Get ancestors correctly
   - Prevent circular references

4. **Edge Cases**
   - Very deep hierarchies (50+ levels)
   - Many children (1000+)
   - Concurrent operations

```python
# Example test structure
class TestTaskService:
    async def test_create_task_success(self):
        ...

    async def test_create_child_task_generates_hierarchical_id(self):
        ...

    async def test_close_task_blocked_by_open_children(self):
        ...

    async def test_close_subtask_requires_validation(self):
        ...

    async def test_reopen_task_propagates_to_parent(self):
        ...

    async def test_get_ancestors_returns_path_to_root(self):
        ...
```
