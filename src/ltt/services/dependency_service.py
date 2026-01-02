"""
Dependency service for the Learning Task Tracker.

Manages task dependencies, blocking logic, and ready work detection.
All blocking queries are learner-scoped per ADR-001.
"""

import json
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import (
    Dependency,
    DependencyModel,
    DependencyType,
    Task,
    TaskModel,
)

# ============================================================================
# Exceptions
# ============================================================================


class DependencyError(Exception):
    """Base exception for dependency operations."""


class CycleError(DependencyError):
    """Adding this dependency would create a cycle."""

    def __init__(self, message: str, cycle: list[str] | None = None):
        self.cycle = cycle
        super().__init__(message)


class DuplicateError(DependencyError):
    """Dependency already exists."""


class DependencyNotFoundError(DependencyError):
    """Dependency does not exist."""


class TaskNotFoundError(DependencyError):
    """Referenced task does not exist."""


# ============================================================================
# Constants
# ============================================================================

BLOCKING_TYPES = {DependencyType.BLOCKS, DependencyType.PARENT_CHILD}


# ============================================================================
# CRUD Operations
# ============================================================================


async def add_dependency(
    session: AsyncSession,
    task_id: str,
    depends_on_id: str,
    dependency_type: DependencyType = DependencyType.BLOCKS,
    actor: str = "system",
    metadata: dict[str, Any] | None = None,
) -> Dependency:
    """
    Create a dependency relationship.

    Args:
        session: Database session
        task_id: The task that depends on another
        depends_on_id: The task being depended upon
        dependency_type: Type of relationship
        actor: Who created this dependency
        metadata: Optional type-specific data

    Returns:
        Created dependency

    Raises:
        TaskNotFoundError: If either task doesn't exist
        CycleError: If this would create a circular dependency
        DuplicateError: If dependency already exists
    """
    # 1. Check both tasks exist
    task_result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = task_result.scalar_one_or_none()

    depends_on_result = await session.execute(
        select(TaskModel).where(TaskModel.id == depends_on_id)
    )
    depends_on = depends_on_result.scalar_one_or_none()

    if not task:
        raise TaskNotFoundError(f"Task {task_id} does not exist")
    if not depends_on:
        raise TaskNotFoundError(f"Task {depends_on_id} does not exist")

    # 2. Check not already exists
    existing_result = await session.execute(
        select(DependencyModel)
        .where(DependencyModel.task_id == task_id)
        .where(DependencyModel.depends_on_id == depends_on_id)
    )
    if existing_result.scalar_one_or_none():
        raise DuplicateError(f"Dependency {task_id} -> {depends_on_id} already exists")

    # 3. Check for cycles (only for blocking types)
    if dependency_type in BLOCKING_TYPES:
        if await would_create_cycle(session, task_id, depends_on_id):
            raise CycleError(f"Adding dependency {task_id} -> {depends_on_id} would create a cycle")

    # 4. Create the dependency
    dep = DependencyModel(
        task_id=task_id,
        depends_on_id=depends_on_id,
        dependency_type=dependency_type.value,
        dep_metadata=json.dumps(metadata) if metadata else "{}",
        created_by=actor,
    )
    session.add(dep)

    try:
        await session.commit()
        await session.refresh(dep)
    except IntegrityError as e:
        await session.rollback()
        raise DuplicateError(f"Dependency already exists: {e}") from e

    # Map dep_metadata to metadata for Pydantic model
    return Dependency(
        task_id=dep.task_id,
        depends_on_id=dep.depends_on_id,
        dependency_type=DependencyType(dep.dependency_type),
        metadata=json.loads(dep.dep_metadata) if dep.dep_metadata else None,
        created_at=dep.created_at,
        created_by=dep.created_by,
    )


async def remove_dependency(
    session: AsyncSession,
    task_id: str,
    depends_on_id: str,
) -> None:
    """
    Remove a dependency relationship.

    Args:
        session: Database session
        task_id: The dependent task
        depends_on_id: The dependency to remove

    Raises:
        DependencyNotFoundError: If dependency doesn't exist
    """
    result = await session.execute(
        select(DependencyModel)
        .where(DependencyModel.task_id == task_id)
        .where(DependencyModel.depends_on_id == depends_on_id)
    )
    dep = result.scalar_one_or_none()

    if not dep:
        raise DependencyNotFoundError(f"Dependency {task_id} -> {depends_on_id} does not exist")

    await session.delete(dep)
    await session.commit()


async def get_dependencies(
    session: AsyncSession,
    task_id: str,
    dependency_type: DependencyType | None = None,
) -> list[Dependency]:
    """
    Get dependencies for a task (what it depends on).

    Args:
        session: Database session
        task_id: Task to check
        dependency_type: Filter by type (None = all)

    Returns:
        List of dependencies
    """
    query = select(DependencyModel).where(DependencyModel.task_id == task_id)

    if dependency_type:
        query = query.where(DependencyModel.dependency_type == dependency_type.value)

    result = await session.execute(query)
    deps = result.scalars().all()

    return [
        Dependency(
            task_id=dep.task_id,
            depends_on_id=dep.depends_on_id,
            dependency_type=DependencyType(dep.dependency_type),
            metadata=json.loads(dep.dep_metadata) if dep.dep_metadata else None,
            created_at=dep.created_at,
            created_by=dep.created_by,
        )
        for dep in deps
    ]


async def get_dependents(
    session: AsyncSession,
    task_id: str,
    dependency_type: DependencyType | None = None,
) -> list[Dependency]:
    """
    Get dependents of a task (what depends on it).

    Args:
        session: Database session
        task_id: Task to check
        dependency_type: Filter by type (None = all)

    Returns:
        List of dependencies where this task is depended upon
    """
    query = select(DependencyModel).where(DependencyModel.depends_on_id == task_id)

    if dependency_type:
        query = query.where(DependencyModel.dependency_type == dependency_type.value)

    result = await session.execute(query)
    deps = result.scalars().all()

    return [
        Dependency(
            task_id=dep.task_id,
            depends_on_id=dep.depends_on_id,
            dependency_type=DependencyType(dep.dependency_type),
            metadata=json.loads(dep.dep_metadata) if dep.dep_metadata else None,
            created_at=dep.created_at,
            created_by=dep.created_by,
        )
        for dep in deps
    ]


# ============================================================================
# Blocking Analysis (Learner-Scoped)
# ============================================================================


async def get_blocking_tasks(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
) -> list[Task]:
    """
    Get tasks that are currently blocking this task for a learner.

    Only returns blockers not closed by this learner.

    Args:
        session: Database session
        task_id: Task to check
        learner_id: Learner whose progress to check

    Returns:
        List of blocking tasks (not closed by learner)
    """
    query = text("""
        SELECT DISTINCT t.*
        FROM tasks t
        JOIN dependencies d ON d.depends_on_id = t.id
        LEFT JOIN learner_task_progress ltp
          ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
        WHERE d.task_id = :task_id
          AND d.dependency_type IN ('blocks', 'parent_child')
          AND COALESCE(ltp.status, 'open') != 'closed'
    """)

    result = await session.execute(
        query,
        {"task_id": task_id, "learner_id": learner_id},
    )

    tasks = []
    for row in result.mappings():
        tasks.append(Task.model_validate(dict(row)))

    return tasks


async def is_task_blocked(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
) -> tuple[bool, list[Task]]:
    """
    Check if a task is blocked for a learner.

    Args:
        session: Database session
        task_id: Task to check
        learner_id: Learner whose progress to check

    Returns:
        (is_blocked, blocking_tasks)
    """
    blocking_tasks = await get_blocking_tasks(session, task_id, learner_id)
    return len(blocking_tasks) > 0, blocking_tasks


async def is_task_ready(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
) -> bool:
    """
    Check if a task is ready to work on for a learner.

    A task is ready if:
    - Learner's status is 'open' or 'in_progress'
    - No blocking dependencies are open for learner

    Args:
        session: Database session
        task_id: Task to check
        learner_id: Learner whose progress to check

    Returns:
        True if task can be worked on by learner
    """
    # Check learner status
    query = text("""
        SELECT COALESCE(ltp.status, 'open') as status
        FROM tasks t
        LEFT JOIN learner_task_progress ltp
          ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
        WHERE t.id = :task_id
    """)

    result = await session.execute(
        query,
        {"task_id": task_id, "learner_id": learner_id},
    )
    row = result.fetchone()

    if not row:
        return False

    status = row[0]
    if status not in ("open", "in_progress"):
        return False

    # Check if blocked
    is_blocked, _ = await is_task_blocked(session, task_id, learner_id)
    return not is_blocked


# ============================================================================
# Ready Work Detection
# ============================================================================


async def get_ready_work(
    session: AsyncSession,
    project_id: str,
    learner_id: str,
    task_type: str | None = None,
    limit: int = 10,
) -> list[Task]:
    """
    Get tasks that are unblocked and ready to work on for a learner.

    This is the primary query for "what should I do next?"

    Filters:
    - Learner's status is 'open' or 'in_progress'
    - No blocking dependencies that are open for learner
    - Optionally filtered by task_type

    Ordering:
    - In-progress tasks first
    - Priority (lower first: P0, P1, P2...)
    - Hierarchy depth (parents before children)
    - Creation date (older first)

    Args:
        session: Database session
        project_id: Scope to project
        learner_id: Learner to get ready work for
        task_type: Filter by type (task, subtask, etc.)
        limit: Maximum results

    Returns:
        List of ready tasks with learner's progress
    """
    # Build the task_type filter conditionally
    task_type_filter = "AND t.task_type = :task_type" if task_type else ""

    query = text(f"""
        WITH RECURSIVE
        -- Tasks directly blocked by 'blocks' dependencies
        blocked_directly AS (
            SELECT DISTINCT d.task_id
            FROM dependencies d
            LEFT JOIN learner_task_progress ltp_blocker
              ON ltp_blocker.task_id = d.depends_on_id
              AND ltp_blocker.learner_id = :learner_id
            WHERE d.dependency_type = 'blocks'
              AND COALESCE(ltp_blocker.status, 'open') != 'closed'
        ),
        -- Propagate blocking to children via parent_id hierarchy
        blocked_with_children AS (
            SELECT task_id FROM blocked_directly
            UNION
            SELECT t.id
            FROM blocked_with_children bwc
            JOIN tasks t ON t.parent_id = bwc.task_id
        )
        SELECT
          t.*
        FROM tasks t
        LEFT JOIN learner_task_progress ltp
          ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
        WHERE t.project_id = :project_id
          AND COALESCE(ltp.status, 'open') IN ('open', 'in_progress')
          {task_type_filter}
          AND NOT EXISTS (
            SELECT 1 FROM blocked_with_children bwc WHERE bwc.task_id = t.id
          )
        ORDER BY
          CASE COALESCE(ltp.status, 'open')
            WHEN 'in_progress' THEN 0
            WHEN 'open' THEN 1
          END,
          t.priority ASC,
          length(t.id) - length(replace(t.id, '.', '')) ASC,
          t.created_at ASC
        LIMIT :limit
    """)

    params = {
        "project_id": project_id,
        "learner_id": learner_id,
        "limit": limit,
    }
    if task_type:
        params["task_type"] = task_type

    result = await session.execute(query, params)

    tasks = []
    for row in result.mappings():
        tasks.append(Task.model_validate(dict(row)))

    return tasks


async def get_blocked_tasks(
    session: AsyncSession,
    project_id: str,
    learner_id: str,
) -> list[tuple[Task, list[Task]]]:
    """
    Get all blocked tasks with their blockers for a learner.

    Args:
        session: Database session
        project_id: Scope to project
        learner_id: Learner whose blocked tasks to check

    Returns:
        List of (blocked_task, blocking_tasks) tuples
    """
    # Get all tasks with blocked status for this learner
    query = text("""
        SELECT DISTINCT t.*
        FROM tasks t
        LEFT JOIN learner_task_progress ltp
          ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
        WHERE t.project_id = :project_id
          AND COALESCE(ltp.status, 'open') = 'blocked'
    """)

    result = await session.execute(
        query,
        {"project_id": project_id, "learner_id": learner_id},
    )

    blocked_tasks_with_blockers = []

    for row in result.mappings():
        task = Task.model_validate(dict(row))
        blockers = await get_blocking_tasks(session, task.id, learner_id)
        blocked_tasks_with_blockers.append((task, blockers))

    return blocked_tasks_with_blockers


# ============================================================================
# Cycle Detection
# ============================================================================


async def would_create_cycle(
    session: AsyncSession,
    task_id: str,
    depends_on_id: str,
) -> bool:
    """
    Check if adding this dependency would create a cycle.

    Uses recursive CTE to check if depends_on_id can reach task_id.
    If it can, adding this edge would close a cycle.

    Args:
        session: Database session
        task_id: Task that would depend
        depends_on_id: Task to depend on

    Returns:
        True if this would create a cycle
    """
    if task_id == depends_on_id:
        return True  # Self-loop

    # Check if depends_on_id can reach task_id via existing dependencies
    query = text("""
        WITH RECURSIVE reachable AS (
            -- Start from the would-be dependency target
            SELECT depends_on_id as task_id, 1 as depth
            FROM dependencies
            WHERE task_id = :depends_on_id
              AND dependency_type IN ('blocks', 'parent_child')

            UNION ALL

            -- Follow transitive dependencies
            SELECT d.depends_on_id, r.depth + 1
            FROM dependencies d
            JOIN reachable r ON d.task_id = r.task_id
            WHERE d.dependency_type IN ('blocks', 'parent_child')
              AND r.depth < 100  -- Safety limit
        )
        SELECT EXISTS (
            SELECT 1 FROM reachable WHERE task_id = :task_id
        ) as would_cycle
    """)

    result = await session.execute(
        query,
        {"task_id": task_id, "depends_on_id": depends_on_id},
    )
    row = result.fetchone()
    return bool(row[0]) if row else False


async def detect_cycles(
    session: AsyncSession,
    project_id: str,
) -> list[list[str]]:
    """
    Detect all cycles in the dependency graph using Tarjan's algorithm.

    Args:
        session: Database session
        project_id: Scope to project

    Returns:
        List of cycles, each a list of task IDs in the cycle
    """
    # Get all tasks in project
    tasks_result = await session.execute(
        select(TaskModel.id).where(TaskModel.project_id == project_id)
    )
    all_tasks = {row[0] for row in tasks_result.fetchall()}

    # Get all dependencies (blocking types only)
    deps_result = await session.execute(
        select(DependencyModel.task_id, DependencyModel.depends_on_id).where(
            DependencyModel.dependency_type.in_(["blocks", "parent_child"])
        )
    )
    edges = [(row[0], row[1]) for row in deps_result.fetchall()]

    # Build adjacency list
    graph: dict[str, list[str]] = {t: [] for t in all_tasks}
    for task_id, depends_on_id in edges:
        if task_id in graph:
            graph[task_id].append(depends_on_id)

    # Tarjan's SCC algorithm
    index_counter = [0]
    stack: list[str] = []
    lowlinks: dict[str, int] = {}
    index: dict[str, int] = {}
    on_stack: set[str] = set()
    sccs: list[list[str]] = []

    def strongconnect(node: str) -> None:
        index[node] = index_counter[0]
        lowlinks[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in graph.get(node, []):
            if neighbor not in index:
                strongconnect(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], index[neighbor])

        if lowlinks[node] == index[node]:
            scc = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.append(w)
                if w == node:
                    break
            if len(scc) > 1:  # Only cycles have > 1 node
                sccs.append(scc)

    for node in all_tasks:
        if node not in index:
            strongconnect(node)

    return sccs
