# Dependencies Module

> Dependency management, blocking logic, and ready work detection.

**Architecture Note**: This module implements the two-layer architecture from [ADR-001](./adr/001-learner-scoped-task-progress.md). Blocking queries check learner-specific progress, not template task status.

## Overview

This module manages relationships between tasks that control workflow order:
- Which tasks block other tasks
- Detecting cycles to prevent deadlocks
- Calculating "ready work" (unblocked tasks per learner)
- Propagating blocking through hierarchy

### Reference: Beads Implementation

Key files:
- [internal/storage/sqlite/dependencies.go](../internal/storage/sqlite/dependencies.go) - Core dependency operations
- [internal/storage/sqlite/ready.go](../internal/storage/sqlite/ready.go) - Ready work calculation
- [internal/types/types.go:498-551](../internal/types/types.go) - Dependency types

---

## 1. Dependency Types

```python
from enum import Enum


class DependencyType(str, Enum):
    """
    Type of relationship between tasks.

    BLOCKS: Task cannot start until dependency is closed.
            Used for explicit ordering (Task B waits for Task A).

    PARENT_CHILD: Hierarchical relationship.
                  Implicit: parent can't close until children close.
                  Created automatically when tasks are nested.

    RELATED: Informational link, no blocking effect.
             Used for cross-references and context.
    """
    BLOCKS = "blocks"
    PARENT_CHILD = "parent_child"
    RELATED = "related"


# Which types affect ready work calculation
BLOCKING_TYPES = {DependencyType.BLOCKS, DependencyType.PARENT_CHILD}
```

---

## 2. Service Interface

```python
from typing import List, Optional, Tuple
from ltt.models import (
    Dependency, DependencyCreate, DependencyType,
    Task, TaskSummary, TaskStatus
)


class DependencyService:
    """
    Service for dependency management.

    Handles blocking relationships, ready work detection,
    and cycle prevention.
    """

    def __init__(self, db_session, event_service: "EventService"):
        self.db = db_session
        self.events = event_service

    # ─────────────────────────────────────────────────────────────
    # CRUD Operations
    # ─────────────────────────────────────────────────────────────

    async def add_dependency(
        self,
        task_id: str,
        depends_on_id: str,
        dependency_type: DependencyType = DependencyType.BLOCKS,
        actor: str = "system",
        metadata: Optional[dict] = None
    ) -> Dependency:
        """
        Create a dependency relationship.

        Args:
            task_id: The task that depends on another
            depends_on_id: The task being depended upon
            dependency_type: Type of relationship
            actor: Who created this dependency
            metadata: Optional type-specific data

        Returns:
            Created dependency

        Raises:
            NotFoundError: If either task doesn't exist
            CycleError: If this would create a circular dependency
            DuplicateError: If dependency already exists
        """
        ...

    async def remove_dependency(
        self,
        task_id: str,
        depends_on_id: str,
        actor: str
    ) -> None:
        """
        Remove a dependency relationship.

        Args:
            task_id: The dependent task
            depends_on_id: The dependency to remove
            actor: Who removed this

        Raises:
            NotFoundError: If dependency doesn't exist
        """
        ...

    async def get_dependencies(
        self,
        task_id: str,
        dependency_type: Optional[DependencyType] = None
    ) -> List[Dependency]:
        """
        Get dependencies for a task (what it depends on).

        Args:
            task_id: Task to check
            dependency_type: Filter by type (None = all)

        Returns:
            List of dependencies
        """
        ...

    async def get_dependents(
        self,
        task_id: str,
        dependency_type: Optional[DependencyType] = None
    ) -> List[Dependency]:
        """
        Get dependents of a task (what depends on it).

        Args:
            task_id: Task to check
            dependency_type: Filter by type (None = all)

        Returns:
            List of dependencies where this task is depended upon
        """
        ...

    # ─────────────────────────────────────────────────────────────
    # Blocking Analysis
    # ─────────────────────────────────────────────────────────────

    async def get_blocking_tasks(
        self,
        task_id: str,
        learner_id: str
    ) -> List[TaskSummary]:
        """
        Get tasks that are currently blocking this task for a learner.

        Only returns blockers not closed by this learner.

        Args:
            task_id: Task to check
            learner_id: Learner whose progress to check

        Returns:
            List of blocking tasks (not closed by learner)
        """
        ...

    async def is_task_blocked(
        self,
        task_id: str,
        learner_id: str
    ) -> Tuple[bool, List[TaskSummary]]:
        """
        Check if a task is blocked for a learner.

        Args:
            task_id: Task to check
            learner_id: Learner whose progress to check

        Returns:
            (is_blocked, blocking_tasks)
        """
        ...

    async def is_task_ready(
        self,
        task_id: str,
        learner_id: str
    ) -> bool:
        """
        Check if a task is ready to work on for a learner.

        A task is ready if:
        - Learner's status is 'open' or 'in_progress'
        - No blocking dependencies are open for learner
        - No parent has open siblings with lower priority for learner

        Args:
            task_id: Task to check
            learner_id: Learner whose progress to check

        Returns:
            True if task can be worked on by learner
        """
        ...

    # ─────────────────────────────────────────────────────────────
    # Ready Work Detection
    # ─────────────────────────────────────────────────────────────

    async def get_ready_work(
        self,
        project_id: str,
        learner_id: str,
        task_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Task]:
        """
        Get tasks that are unblocked and ready to work on for a learner.

        This is the primary query for "what should I do next?"

        Filters:
        - Learner's status is 'open' (not in_progress, blocked, or closed)
        - No blocking dependencies that are open for learner
        - Optionally filtered by task_type

        Ordering:
        - In-progress tasks first (if status changed to in_progress)
        - Priority (lower first: P0, P1, P2...)
        - Hierarchy depth (parents before children)
        - Creation date (older first)

        Args:
            project_id: Scope to project
            learner_id: Learner to get ready work for
            task_type: Filter by type (task, subtask, etc.)
            limit: Maximum results

        Returns:
            List of ready tasks with learner's progress
        """
        ...

    async def get_blocked_tasks(
        self,
        project_id: str,
        learner_id: str
    ) -> List[Tuple[Task, List[TaskSummary]]]:
        """
        Get all blocked tasks with their blockers for a learner.

        Args:
            project_id: Scope to project
            learner_id: Learner whose blocked tasks to check

        Returns:
            List of (blocked_task, blocking_tasks) tuples
        """
        ...

    # ─────────────────────────────────────────────────────────────
    # Cycle Detection
    # ─────────────────────────────────────────────────────────────

    async def would_create_cycle(
        self,
        task_id: str,
        depends_on_id: str
    ) -> bool:
        """
        Check if adding this dependency would create a cycle.

        Args:
            task_id: Task that would depend
            depends_on_id: Task to depend on

        Returns:
            True if this would create a cycle
        """
        ...

    async def detect_cycles(
        self,
        project_id: str
    ) -> List[List[str]]:
        """
        Detect all cycles in the dependency graph.

        Used for diagnostics and repair.

        Args:
            project_id: Scope to project

        Returns:
            List of cycles, each a list of task IDs in the cycle
        """
        ...
```

---

## 3. Ready Work Algorithm

**Per-Learner Ready Work Query** (implements ADR-001):

```sql
-- PostgreSQL version: checks learner's progress, not template status
WITH RECURSIVE
  -- Step 1: Find tasks blocking this learner
  -- A blocker is open if the learner hasn't closed it
  blocked_directly AS (
    SELECT DISTINCT d.task_id
    FROM dependencies d
    LEFT JOIN learner_task_progress ltp_blocker
      ON ltp_blocker.task_id = d.depends_on_id
      AND ltp_blocker.learner_id = :learner_id
    WHERE d.dependency_type IN ('blocks', 'parent_child')
      AND COALESCE(ltp_blocker.status, 'open') != 'closed'
  ),

  -- Step 2: Propagate blocking through parent-child hierarchy
  -- If a parent is blocked for learner, children are also blocked
  blocked_transitively AS (
    -- Base: directly blocked
    SELECT task_id, 0 as depth
    FROM blocked_directly

    UNION ALL

    -- Recursive: children of blocked tasks inherit blocking
    SELECT d.task_id, bt.depth + 1
    FROM blocked_transitively bt
    JOIN dependencies d ON d.depends_on_id = bt.task_id
    WHERE d.dependency_type = 'parent_child'
      AND bt.depth < 50  -- Safety limit
  )

-- Step 3: Select tasks open for learner that are not blocked
SELECT
  t.*,
  COALESCE(ltp.status, 'open') as learner_status
FROM tasks t
LEFT JOIN learner_task_progress ltp
  ON ltp.task_id = t.id
  AND ltp.learner_id = :learner_id
WHERE t.project_id = :project_id
  AND COALESCE(ltp.status, 'open') IN ('open', 'in_progress')
  AND NOT EXISTS (
    SELECT 1 FROM blocked_transitively bt WHERE bt.task_id = t.id
  )
ORDER BY
  CASE COALESCE(ltp.status, 'open')
    WHEN 'in_progress' THEN 0
    WHEN 'open' THEN 1
  END,
  t.priority ASC,           -- P0 first
  length(t.id) - length(replace(t.id, '.', '')) ASC,  -- Shallower first
  t.created_at ASC          -- Older first
LIMIT :limit
```

### Python Implementation

```python
async def get_ready_work(
    db,
    project_id: str,
    learner_id: str,
    task_type: Optional[str] = None,
    limit: int = 10
) -> List[Task]:
    """
    Get unblocked tasks ready to work on for a learner.

    Implements ADR-001: Checks learner_task_progress, not task.status
    """
    query = text("""
        WITH RECURSIVE
        blocked_directly AS (
            SELECT DISTINCT d.task_id
            FROM dependencies d
            LEFT JOIN learner_task_progress ltp_blocker
              ON ltp_blocker.task_id = d.depends_on_id
              AND ltp_blocker.learner_id = :learner_id
            WHERE d.dependency_type IN ('blocks', 'parent_child')
              AND COALESCE(ltp_blocker.status, 'open') != 'closed'
        ),
        blocked_transitively AS (
            SELECT task_id, 0 as depth FROM blocked_directly
            UNION ALL
            SELECT d.task_id, bt.depth + 1
            FROM blocked_transitively bt
            JOIN dependencies d ON d.depends_on_id = bt.task_id
            WHERE d.dependency_type = 'parent_child' AND bt.depth < 50
        )
        SELECT
          t.*,
          COALESCE(ltp.status, 'open') as learner_status
        FROM tasks t
        LEFT JOIN learner_task_progress ltp
          ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
        WHERE t.project_id = :project_id
          AND COALESCE(ltp.status, 'open') IN ('open', 'in_progress')
          AND (:task_type IS NULL OR t.task_type = :task_type)
          AND NOT EXISTS (
            SELECT 1 FROM blocked_transitively bt WHERE bt.task_id = t.id
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

    result = await db.execute(query, {
        "project_id": project_id,
        "learner_id": learner_id,
        "task_type": task_type,
        "limit": limit
    })

    return [Task.model_validate(row) for row in result.fetchall()]
```

---

## 4. Cycle Detection

### Check Before Adding

```python
async def would_create_cycle(
    db,
    task_id: str,
    depends_on_id: str
) -> bool:
    """
    Check if adding task_id -> depends_on_id would create a cycle.

    Uses BFS to check if depends_on_id can reach task_id.
    If it can, adding this edge would close a cycle.
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

    result = await db.execute(query, {
        "task_id": task_id,
        "depends_on_id": depends_on_id
    })
    row = result.fetchone()
    return row.would_cycle if row else False
```

### Detect All Cycles

```python
async def detect_cycles(db, project_id: str) -> List[List[str]]:
    """
    Find all cycles in the dependency graph using Tarjan's algorithm.

    Returns list of cycles, each cycle is a list of task IDs.
    """
    # Get all tasks and dependencies
    tasks_result = await db.execute(
        select(TaskModel.id).where(TaskModel.project_id == project_id)
    )
    all_tasks = {row[0] for row in tasks_result.fetchall()}

    deps_result = await db.execute(
        select(DependencyModel.task_id, DependencyModel.depends_on_id)
        .where(DependencyModel.dependency_type.in_(['blocks', 'parent_child']))
    )
    edges = {(row[0], row[1]) for row in deps_result.fetchall()}

    # Build adjacency list
    graph = {t: [] for t in all_tasks}
    for task_id, depends_on_id in edges:
        if task_id in graph:
            graph[task_id].append(depends_on_id)

    # Tarjan's SCC algorithm
    index_counter = [0]
    stack = []
    lowlinks = {}
    index = {}
    on_stack = set()
    sccs = []

    def strongconnect(node):
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
```

---

## 5. Dependency Creation with Validation

```python
async def add_dependency(
    db,
    task_id: str,
    depends_on_id: str,
    dependency_type: DependencyType,
    actor: str,
    metadata: Optional[dict] = None,
    event_service: Optional[EventService] = None
) -> Dependency:
    """
    Add a dependency with full validation.
    """
    # 1. Check both tasks exist
    task = await db.get(TaskModel, task_id)
    depends_on = await db.get(TaskModel, depends_on_id)

    if not task:
        raise NotFoundError(task_id)
    if not depends_on:
        raise NotFoundError(depends_on_id)

    # 2. Check not already exists
    existing = await db.execute(
        select(DependencyModel)
        .where(DependencyModel.task_id == task_id)
        .where(DependencyModel.depends_on_id == depends_on_id)
    )
    if existing.scalar_one_or_none():
        raise DuplicateError(f"Dependency {task_id} -> {depends_on_id} already exists")

    # 3. Check for cycles (only for blocking types)
    if dependency_type in BLOCKING_TYPES:
        if await would_create_cycle(db, task_id, depends_on_id):
            raise CycleError(
                f"Adding dependency {task_id} -> {depends_on_id} would create a cycle"
            )

    # 4. Create the dependency
    dep = DependencyModel(
        task_id=task_id,
        depends_on_id=depends_on_id,
        dependency_type=dependency_type.value,
        metadata=json.dumps(metadata) if metadata else "{}",
        created_by=actor
    )
    db.add(dep)

    # 5. Status updates are now per-learner (ADR-001)
    # No need to modify task.status - it doesn't exist on template
    # Blocking is determined dynamically via learner_task_progress joins

    # 6. Record event
    if event_service:
        await event_service.record(
            entity_type="task",
            entity_id=task_id,
            event_type=EventType.DEPENDENCY_ADDED,
            actor=actor,
            new_value=depends_on_id
        )

    await db.commit()
    return Dependency.model_validate(dep)
```

---

## 6. Status Propagation

**Note**: With ADR-001, status propagation is per-learner and implicit. When a learner closes a task, dependent tasks become unblocked automatically via the ready work query. No explicit status updates needed.

```python
async def handle_dependency_closed(
    db,
    closed_task_id: str,
    learner_id: str,
    actor: str
) -> List[str]:
    """
    Handle a task being closed by a learner: identify dependents that may now be unblocked.

    With ADR-001, blocking is determined dynamically via joins.
    This function returns potentially unblocked tasks for notification purposes.

    Returns list of task IDs that are now unblocked for this learner.
    """
    # Find tasks that were potentially blocked by this task
    result = await db.execute(
        select(DependencyModel.task_id)
        .where(DependencyModel.depends_on_id == closed_task_id)
        .where(DependencyModel.dependency_type.in_(['blocks', 'parent_child']))
    )
    dependent_ids = [row[0] for row in result.fetchall()]

    newly_unblocked = []

    for dep_id in dependent_ids:
        # Check if this task is now unblocked for learner
        is_blocked, blockers = await is_task_blocked(db, dep_id, learner_id)

        if not is_blocked:
            # Task is now unblocked - no status update needed
            # (blocking is determined dynamically by ready work query)
            newly_unblocked.append(dep_id)

    return newly_unblocked
```

---

## 7. Error Types

```python
class DependencyError(Exception):
    """Base exception for dependency operations."""
    pass


class CycleError(DependencyError):
    """Adding this dependency would create a cycle."""
    def __init__(self, message: str, cycle: Optional[List[str]] = None):
        self.cycle = cycle
        super().__init__(message)


class DuplicateError(DependencyError):
    """Dependency already exists."""
    pass
```

---

## 8. Database Queries Reference

### Get Blocked Tasks with Blockers (Per-Learner)

```sql
-- Tasks blocked for a specific learner
SELECT
    t.*,
    COALESCE(ltp.status, 'open') as learner_status,
    array_agg(blocker.id) as blocker_ids,
    array_agg(blocker.title) as blocker_titles
FROM tasks t
LEFT JOIN learner_task_progress ltp
    ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
JOIN dependencies d ON t.id = d.task_id
JOIN tasks blocker ON d.depends_on_id = blocker.id
LEFT JOIN learner_task_progress ltp_blocker
    ON ltp_blocker.task_id = blocker.id AND ltp_blocker.learner_id = :learner_id
WHERE t.project_id = :project_id
  AND COALESCE(ltp.status, 'open') = 'blocked'
  AND d.dependency_type IN ('blocks', 'parent_child')
  AND COALESCE(ltp_blocker.status, 'open') != 'closed'
GROUP BY t.id, ltp.status
```

### Dependency Tree Visualization

```sql
-- Get full dependency tree from a root task
WITH RECURSIVE dep_tree AS (
    SELECT
        t.id,
        t.title,
        t.status,
        0 as depth,
        ARRAY[t.id] as path
    FROM tasks t
    WHERE t.id = :root_id

    UNION ALL

    SELECT
        child.id,
        child.title,
        child.status,
        dt.depth + 1,
        dt.path || child.id
    FROM dep_tree dt
    JOIN dependencies d ON d.depends_on_id = dt.id
    JOIN tasks child ON d.task_id = child.id
    WHERE dt.depth < 20
      AND NOT child.id = ANY(dt.path)  -- Prevent cycles
)
SELECT * FROM dep_tree ORDER BY path
```

---

## 9. File Structure

```
src/ltt/services/
├── dependency.py      # DependencyService
├── exceptions.py      # CycleError, DuplicateError
└── utils/
    └── graph.py       # Cycle detection algorithms
```

---

## 10. Testing Requirements

```python
class TestDependencyService:
    async def test_add_blocking_dependency(self):
        """Adding blocks dependency affects ready work for learners."""
        ...

    async def test_cycle_detection_prevents_circular(self):
        """Cannot create A->B->C->A cycle."""
        ...

    async def test_ready_work_excludes_blocked_per_learner(self):
        """Ready work only returns unblocked tasks for specific learner."""
        ...

    async def test_closing_blocker_unblocks_dependent_per_learner(self):
        """When learner closes blocker, dependent becomes ready for that learner."""
        ...

    async def test_transitive_blocking_per_learner(self):
        """If A blocks B, and B blocks C for learner, then C is blocked for learner."""
        ...

    async def test_parent_child_implicit_blocking_per_learner(self):
        """Parent can't be closed by learner until children closed by learner."""
        ...

    async def test_multi_learner_independence(self):
        """Learner A closing task doesn't unblock it for Learner B."""
        # Task 1 blocks Task 2
        # Learner A closes Task 1 -> Task 2 ready for A
        # Task 2 still blocked for Learner B
        ...

    async def test_lazy_progress_initialization(self):
        """Ready work query works when learner has no progress records yet."""
        # New learner, no learner_task_progress records
        # COALESCE(ltp.status, 'open') should return all tasks as 'open'
        ...
```

---

## 11. ADR-001 Migration Summary

### Key Changes from Template-Only Model

**Before (Single-Layer)**:
- `tasks.status` tracked completion state
- Blocking queries: `JOIN tasks blocker WHERE blocker.status != 'closed'`
- One learner closing a task closed it for everyone

**After (Two-Layer with ADR-001)**:
- `tasks` = template (no status column)
- `learner_task_progress` = per-learner status
- Blocking queries: `LEFT JOIN learner_task_progress ltp WHERE COALESCE(ltp.status, 'open') != 'closed'`
- Each learner has independent progress

### Query Pattern

All blocking/ready work queries follow this pattern:

```sql
-- Template: Check if blocker task is closed
WHERE blocker.status != 'closed'

-- Instance (ADR-001): Check if blocker is closed BY THIS LEARNER
LEFT JOIN learner_task_progress ltp
  ON ltp.task_id = blocker.id AND ltp.learner_id = :learner_id
WHERE COALESCE(ltp.status, 'open') != 'closed'
```

The `COALESCE(ltp.status, 'open')` pattern handles lazy initialization: if no progress record exists, treat the task as 'open'.

### API Changes

All learner-facing functions now require `learner_id`:

| Function | Before | After |
|----------|--------|-------|
| `get_ready_work` | `(project_id)` | `(project_id, learner_id)` |
| `is_task_blocked` | `(task_id)` | `(task_id, learner_id)` |
| `get_blocking_tasks` | `(task_id)` | `(task_id, learner_id)` |
| `is_task_ready` | `(task_id)` | `(task_id, learner_id)` |
| `get_blocked_tasks` | `(project_id)` | `(project_id, learner_id)` |

### What Stays the Same

Dependency management (template layer) is unchanged:

- `add_dependency(task_id, depends_on_id)` - no learner_id needed
- `remove_dependency(task_id, depends_on_id)` - operates on template
- `would_create_cycle(task_id, depends_on_id)` - template-level check
- Cycle detection operates on dependency graph (template layer)

Dependencies are curriculum structure. Progress is learner-specific.
