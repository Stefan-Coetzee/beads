# ADR-001: Two-Layer Architecture (Template + Instance)

**Status**: Proposed
**Date**: 2025-12-30
**Deciders**: Stefan Coetzee

---

## Context

This learning platform needs to support multiple learners working through the same project independently. A core architectural decision is required:

**How do we separate shared curriculum content from per-learner progress?**

### The Problem

The current design conflates template data with instance data. For example:

```python
class Task:
    id: str
    title: str           # Template data (shared)
    description: str     # Template data (shared)
    status: TaskStatus   # Instance data (per-learner) ← WRONG LAYER
```

If Learner A closes a task, it closes for Learner B. This is fundamentally broken.

---

## Decision

**Adopt a two-layer architecture: Template Layer + Instance Layer.**

### Layer 1: Template Layer (Shared Content)

Defines *what* learners work on. Authored by instructors, shared across all learners.

| Entity | Purpose |
|--------|---------|
| `tasks` | Task definitions (title, description, type, priority, hierarchy) |
| `learning_objectives` | What skills each task teaches (Bloom's taxonomy) |
| `acceptance_criteria` | How to validate successful completion |
| `dependencies` | Prerequisite relationships between tasks |
| `content` | Learning materials (markdown, code samples, links) |

**Key property**: No `learner_id` on any template entity.

### Layer 2: Instance Layer (Per-Learner Progress)

Tracks *how* each learner progresses. Scoped by `learner_id`.

| Entity | Purpose |
|--------|---------|
| `learner_task_progress` | **NEW** - Status per learner per task |
| `submissions` | Learner's work submissions |
| `validations` | Results of validating submissions |
| `status_summaries` | Progress notes and summaries |
| `comments` | Learner-specific comments (with optional learner_id) |

**Key property**: Every instance entity has `learner_id` (or inherits via FK to submission).

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     TEMPLATE LAYER (Shared)                     │
│                                                                 │
│  ┌─────────┐    ┌──────────────┐    ┌────────────────────┐     │
│  │  tasks  │───▶│ learning_    │    │ acceptance_        │     │
│  │         │    │ objectives   │    │ criteria           │     │
│  └────┬────┘    └──────────────┘    └────────────────────┘     │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────┐    ┌─────────┐                                │
│  │dependencies │    │ content │                                │
│  └─────────────┘    └─────────┘                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ task_id (FK)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  INSTANCE LAYER (Per-Learner)                   │
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────┐                    │
│  │learner_task_progress│───▶│  learners   │                    │
│  │ (task_id, learner_id│    │             │                    │
│  │  status, timestamps)│    └──────┬──────┘                    │
│  └─────────────────────┘           │                           │
│                                    │                           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐    │
│  │ submissions │───▶│ validations │    │ status_summaries│    │
│  │(learner_id) │    │(via submit) │    │  (learner_id)   │    │
│  └─────────────┘    └─────────────┘    └─────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ comments (optional learner_id: NULL=shared, set=private)│   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Detailed Changes

### 1. New Model: `LearnerTaskProgress`

```python
class LearnerTaskProgress(BaseModel):
    """Per-learner progress on a task template."""
    id: str
    task_id: str       # FK to template
    learner_id: str    # FK to learner

    status: TaskStatus  # open, in_progress, blocked, closed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime


class LearnerTaskProgressModel(Base):
    __tablename__ = "learner_task_progress"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    learner_id = Column(String, ForeignKey("learners.id", ondelete="CASCADE"), nullable=False)

    status = Column(String, nullable=False, default="open")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    task = relationship("TaskModel", back_populates="learner_progress")
    learner = relationship("LearnerModel", back_populates="task_progress")

    __table_args__ = (
        UniqueConstraint("task_id", "learner_id", name="uq_task_learner_progress"),
        Index("idx_learner_task_progress_task_learner", "task_id", "learner_id"),
        Index("idx_learner_task_progress_learner_status", "learner_id", "status"),
    )
```

### 2. Modified Task Model (Template Only)

Remove all instance-specific fields:

```python
class Task(BaseModel):
    """Task template - shared definition."""
    id: str
    title: str
    description: str
    notes: Optional[str] = None
    task_type: TaskType
    priority: int = 1

    parent_id: Optional[str] = None
    project_id: str

    # NO status - that's in LearnerTaskProgress
    # NO closed_at - that's in LearnerTaskProgress
    # NO close_reason - that's in LearnerTaskProgress

    created_at: datetime
    updated_at: datetime
```

### 3. Modified Comment Model (Dual-Purpose)

Comments can be shared (instructor notes) or per-learner (AI tutor conversation):

```python
class Comment(BaseModel):
    """Comment on a task - optionally scoped to a learner."""
    id: str
    task_id: str
    author: str
    text: str

    # NEW: Optional learner scope
    learner_id: Optional[str] = None  # NULL = visible to all, set = private to learner

    created_at: datetime
```

Query behavior:
- `get_comments(task_id, learner_id)` returns: shared comments (learner_id=NULL) + learner's private comments

### 4. Already Correct (Instance Layer)

These already have `learner_id` and are correctly in the instance layer:

| Entity | learner_id | Notes |
|--------|------------|-------|
| `submissions` | ✓ Direct FK | Already correct |
| `validations` | ✓ Via submission FK | Already correct |
| `status_summaries` | ✓ Direct FK | Already correct |

---

## Query Pattern Changes

### Status Queries Join on Instance Layer

```sql
-- OLD: Get task status (broken - reads template)
SELECT status FROM tasks WHERE id = :task_id;

-- NEW: Get learner's status for a task
SELECT COALESCE(ltp.status, 'open') as status
FROM tasks t
LEFT JOIN learner_task_progress ltp
    ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
WHERE t.id = :task_id;
```

### Ready Work Checks Learner's Progress

```sql
-- Tasks ready for THIS learner (not blocked by incomplete prerequisites)
WITH blocked_for_learner AS (
    SELECT d.task_id
    FROM dependencies d
    LEFT JOIN learner_task_progress ltp
        ON ltp.task_id = d.depends_on_id AND ltp.learner_id = :learner_id
    WHERE d.dependency_type = 'blocks'
      AND COALESCE(ltp.status, 'open') != 'closed'
)
SELECT t.*, COALESCE(ltp.status, 'open') as learner_status
FROM tasks t
LEFT JOIN learner_task_progress ltp
    ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
WHERE t.project_id = :project_id
  AND COALESCE(ltp.status, 'open') IN ('open', 'in_progress')
  AND t.id NOT IN (SELECT task_id FROM blocked_for_learner)
ORDER BY
    CASE COALESCE(ltp.status, 'open')
        WHEN 'in_progress' THEN 0
        WHEN 'open' THEN 1
    END,
    t.priority,
    t.created_at;
```

### Comments Include Shared + Private

```sql
-- Get comments visible to this learner
SELECT * FROM comments
WHERE task_id = :task_id
  AND (learner_id IS NULL OR learner_id = :learner_id)
ORDER BY created_at;
```

---

## Lazy Initialization

Progress records are created on first interaction, not pre-populated:

```python
async def get_or_create_progress(
    db, task_id: str, learner_id: str
) -> LearnerTaskProgress:
    """Get existing progress or create with default status='open'."""
    progress = await db.execute(
        select(LearnerTaskProgressModel)
        .where(
            LearnerTaskProgressModel.task_id == task_id,
            LearnerTaskProgressModel.learner_id == learner_id
        )
    )
    existing = progress.scalar_one_or_none()

    if existing:
        return LearnerTaskProgress.model_validate(existing)

    # Create on first access
    new_progress = LearnerTaskProgressModel(
        id=generate_entity_id("ltp"),
        task_id=task_id,
        learner_id=learner_id,
        status="open"
    )
    db.add(new_progress)
    await db.commit()
    return LearnerTaskProgress.model_validate(new_progress)
```

This avoids pre-creating N×M records (learners × tasks).

---

## SQL Schema

```sql
-- Template Layer
CREATE TABLE tasks (
    id VARCHAR PRIMARY KEY,
    parent_id VARCHAR REFERENCES tasks(id),
    project_id VARCHAR NOT NULL,

    title VARCHAR NOT NULL,
    description TEXT,
    notes TEXT,
    task_type VARCHAR NOT NULL,
    priority INTEGER DEFAULT 1,

    -- NO status column
    -- NO closed_at column
    -- NO close_reason column

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Instance Layer
CREATE TABLE learner_task_progress (
    id VARCHAR PRIMARY KEY,
    task_id VARCHAR REFERENCES tasks(id) ON DELETE CASCADE,
    learner_id VARCHAR REFERENCES learners(id) ON DELETE CASCADE,

    status VARCHAR NOT NULL DEFAULT 'open',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    close_reason TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(task_id, learner_id)
);

-- Modified comments (add optional learner_id)
CREATE TABLE comments (
    id VARCHAR PRIMARY KEY,
    task_id VARCHAR REFERENCES tasks(id) ON DELETE CASCADE,
    learner_id VARCHAR REFERENCES learners(id) ON DELETE CASCADE,  -- NEW: nullable

    author VARCHAR NOT NULL,
    text TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_learner_task_progress_task_learner
    ON learner_task_progress(task_id, learner_id);
CREATE INDEX idx_learner_task_progress_learner_status
    ON learner_task_progress(learner_id, status);
CREATE INDEX idx_comments_task_learner
    ON comments(task_id, learner_id);
```

---

## Files Affected

| File | Changes |
|------|---------|
| `01-data-models.md` | Add LearnerTaskProgress, remove Task.status/closed_at/close_reason, add Comment.learner_id |
| `02-task-management.md` | Status ops use learner_task_progress table |
| `03-dependencies.md` | Blocking checks use learner's progress |
| `05-learning-progress.md` | Progress calculations use new table |
| `07-agent-tools.md` | All status reads/writes use instance layer |
| `PRD.md` | Update schema, algorithms, architecture diagram |

---

## Consequences

### Benefits

1. **Clean separation**: Template authored once, instantiated per learner
2. **No data duplication**: Tasks defined once, progress tracked separately
3. **Instructor changes propagate**: Update a task description, all learners see it
4. **Analytics possible**: Query progress across all learners for a task
5. **Scalable**: Adding learners doesn't duplicate task definitions

### Trade-offs

1. **More joins**: Status queries require joining template + instance tables
2. **Migration complexity**: Existing systems need data migration
3. **Query patterns change**: All code touching status must be updated

### Mitigations

- Use eager loading / joins in common queries
- Create views for common patterns (e.g., `task_with_learner_status`)
- Index on `(task_id, learner_id)` for fast lookups

---

## Alternatives Considered

### 1. Duplicate Tasks Per Learner

Create a copy of every task for each learner.

**Rejected**: Storage bloat (N×M), sync issues when templates change, violates DRY.

### 2. Status as JSON Column

Store `{"learner1": "closed", "learner2": "open"}` on Task.

**Rejected**: Not queryable, no FK constraints, violates 1NF.

### 3. Derive Status from Validations

No explicit status - derive from passing validation.

**Rejected**: Can't distinguish `open` vs `in_progress`, performance cost, inflexible.

---

## Principle

> **Template + Instance separation is a fundamental architectural pattern.**
>
> Any entity that has both "definition" and "per-user state" aspects must be split into two layers. The template layer is authored once and shared. The instance layer tracks each user's interaction with that template.

This applies to:
- Tasks (template) → LearnerTaskProgress (instance)
- Future: Courses (template) → CourseEnrollment (instance)
- Future: Assessments (template) → AssessmentAttempt (instance)

---

## References

- [01-data-models.md](./01-data-models.md) - Current models
- [02-task-management.md](./02-task-management.md) - Status transitions
- [07-agent-tools.md](./07-agent-tools.md) - Agent tool interfaces
