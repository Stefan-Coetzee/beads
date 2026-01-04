# Phase 3: Dependencies - COMPLETED ✅

## Summary

Implemented comprehensive dependency management with cycle detection, learner-scoped blocking, and ready work detection using complex recursive SQL queries.

## What Was Implemented

### 1. Service Layer (`src/ltt/services/dependency_service.py`)

#### **Exception Classes**
- ✅ `DependencyError` - Base exception for dependency operations
- ✅ `CycleError` - Raised when dependency would create circular dependency
- ✅ `DuplicateError` - Raised when dependency already exists
- ✅ `DependencyNotFoundError` - Raised when dependency doesn't exist
- ✅ `TaskNotFoundError` - Raised when referenced task doesn't exist

#### **CRUD Operations**
- ✅ `add_dependency()` - Create dependency with cycle detection and validation
- ✅ `remove_dependency()` - Delete dependency relationships
- ✅ `get_dependencies()` - Get what a task depends on (with type filter)
- ✅ `get_dependents()` - Get what depends on a task (with type filter)

#### **Blocking Analysis (Learner-Scoped per ADR-001)**
- ✅ `get_blocking_tasks()` - Get tasks blocking a task for specific learner
- ✅ `is_task_blocked()` - Check if task is blocked for learner
- ✅ `is_task_ready()` - Check if task is ready to work on for learner

#### **Ready Work Detection**
- ✅ `get_ready_work()` - Complex recursive CTE query for "what should I do next?"
  - Filters by learner status (open/in_progress)
  - Excludes blocked tasks (per learner progress)
  - Excludes transitively blocked tasks
  - Orders by: in_progress first, priority, depth, created_at
  - Supports task_type filtering
- ✅ `get_blocked_tasks()` - Get all blocked tasks with their blockers for learner

#### **Cycle Detection**
- ✅ `would_create_cycle()` - Check if adding dependency would create cycle
  - Uses recursive CTE to traverse dependency graph
  - Prevents circular dependencies before creation
- ✅ `detect_cycles()` - Find all cycles in dependency graph
  - Implements Tarjan's strongly connected components algorithm
  - Returns list of cycles for diagnostics

### 2. Key Architecture Decisions

#### **Learner-Scoped Blocking (ADR-001)**
All blocking queries check `learner_task_progress`, not template task status:

```sql
LEFT JOIN learner_task_progress ltp
  ON ltp.task_id = blocker.id AND ltp.learner_id = :learner_id
WHERE COALESCE(ltp.status, 'open') != 'closed'
```

This ensures:
- Learner A closing a task doesn't unblock it for Learner B
- Lazy initialization: no progress record = status is 'open'
- Each learner has independent workflow

#### **Transitive Blocking**
Recursive CTEs propagate blocking through dependency chains:
- If Task A blocks Task B, and Task B blocks Task C
- Then Task C is also blocked (transitively)
- Implemented via `blocked_transitively` CTE

#### **Conditional SQL Generation**
To handle `task_type` filter with None values:
```python
task_type_filter = "AND t.task_type = :task_type" if task_type else ""
query = text(f"... WHERE ... {task_type_filter} ...")
```

This avoids PostgreSQL parameter type ambiguity issues.

### 3. Tests (`tests/services/test_dependency_service.py`)

**23 comprehensive tests, 95% coverage**

#### CRUD Operations (7 tests)
- ✅ Adding dependencies
- ✅ Removing dependencies
- ✅ Getting dependencies/dependents
- ✅ Error handling (nonexistent tasks, duplicates)

#### Cycle Detection (5 tests)
- ✅ Self-loop detection
- ✅ Two-node cycle (A → B → A)
- ✅ Three-node cycle (A → B → C → A)
- ✅ `would_create_cycle()` helper function
- ✅ `detect_cycles()` finds all cycles

#### Blocking Analysis (6 tests)
- ✅ Getting blocking tasks per learner
- ✅ Checking if task is blocked per learner
- ✅ Checking if task is ready per learner
- ✅ Transitive blocking (A blocks B, B blocks C)
- ✅ Multi-learner independence (A closing doesn't unblock for B)
- ✅ Getting all blocked tasks with blockers

#### Ready Work Detection (5 tests)
- ✅ Excludes blocked tasks per learner
- ✅ Lazy initialization (works with no progress records)
- ✅ Ordering (in_progress, priority, depth, created_at)
- ✅ Task type filtering
- ✅ RELATED dependencies don't block

### 4. Code Quality

- ✅ Ruff linting passing (0 errors)
- ✅ Modern Python 3.12+ type annotations (X | None)
- ✅ Comprehensive docstrings
- ✅ Clean imports and code organization
- ✅ 95% test coverage on dependency_service.py

## Architecture Highlights

### Dependency Types

```python
class DependencyType(str, Enum):
    BLOCKS = "blocks"           # Hard blocking (Task B waits for Task A)
    PARENT_CHILD = "parent_child"  # Hierarchical (auto-created)
    RELATED = "related"         # Informational only
```

**Blocking Types**: Only `BLOCKS` and `PARENT_CHILD` affect ready work calculation.

### Ready Work Query Algorithm

The `get_ready_work()` function uses a two-level recursive CTE:

1. **blocked_directly**: Find tasks with open blockers for this learner
2. **blocked_transitively**: Propagate blocking through parent-child hierarchy
3. **Final SELECT**: Return unblocked tasks ordered by priority

This implements the "what should I do next?" query that powers learner workflows.

### Cycle Prevention

Before adding blocking dependencies, the system:
1. Checks if `depends_on_id` can reach `task_id` via existing edges
2. If yes, adding this edge would close a cycle → reject
3. Uses recursive CTE with depth limit (100) for safety

## Test Coverage

```
Name                                     Stmts   Miss  Cover
--------------------------------------------------------------
src/ltt/services/dependency_service.py     149      7    95%
src/ltt/services/progress_service.py        65      2    97%
src/ltt/services/task_service.py           119      9    92%
--------------------------------------------------------------
TOTAL (services)                           333     18    95%
```

**Test Counts:**
- Phase 1: 3 tests
- Phase 2: 36 tests (39 total)
- Phase 3: 23 tests (**62 total services tests**)

## Files Modified/Created

### Created:
- `src/ltt/services/dependency_service.py` (654 lines)
- `tests/services/test_dependency_service.py` (609 lines)
- `src/ltt/tempdocs/phase3-completed.md` (this file)

### Modified:
- `tests/services/test_progress_service.py` - Fixed unused variable
- `tests/services/test_dependency_service.py` - Fixed status transitions

## Known Issues / Tech Debt

1. **datetime.utcnow() deprecation** (74 warnings)
   - Should migrate to `datetime.now(datetime.UTC)`
   - Affects: `progress_service.py`, `task_service.py`

2. **Missing from 03-dependencies.md spec:**
   - `handle_dependency_closed()` - Notify when dependencies unblock
   - Status propagation helpers (implicit via queries now)
   - Dependency tree visualization queries

3. **Uncovered lines** (7 missing, 95% coverage):
   - Error handling edge cases
   - Some validation branches

## Critical Info for Phase 4

### Learner-Scoped Query Pattern

All learner-facing queries follow this pattern:

```sql
LEFT JOIN learner_task_progress ltp
  ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
WHERE COALESCE(ltp.status, 'open') != 'closed'
```

This handles:
- Lazy initialization (no record = 'open')
- Per-learner status tracking
- Template/instance separation

### Dependency Management

- **Adding dependencies**: Always runs cycle detection for blocking types
- **Removing dependencies**: No cascade (just deletes the relationship)
- **Querying**: Efficient with indexes on (task_id, depends_on_id)

### Graph Algorithms

- **Cycle detection**: Tarjan's SCC algorithm (O(V + E))
- **Ready work**: Recursive CTE (PostgreSQL-optimized)
- **Transitive closure**: Via recursive CTEs with depth limit

## Integration Points

### With Task Service
- Validates tasks exist before adding dependencies
- Cascade deletes when tasks are deleted (foreign key)

### With Progress Service
- All blocking queries check learner_task_progress
- Status transitions affect ready work calculation
- Closing blockers unblocks dependents (dynamically via queries)

### With Future Validation Service (Phase 4)
- Can block submission until dependencies are closed
- Can require tasks to be completed in order
- Can enforce prerequisite chains

## Next: Phase 4 - Validation & Submission

Per the roadmap, Phase 4 will implement:
- Submission management
- Validation rules
- Auto-grading integration
- Acceptance criteria enforcement

**Phase 3: Dependencies - COMPLETE** ✅
- 23 tests passing
- 95% coverage
- All business logic validated
- Cycle detection working
- Learner-scoped blocking implemented
- Ruff linting clean

**Ready for Phase 4!** 🎉
