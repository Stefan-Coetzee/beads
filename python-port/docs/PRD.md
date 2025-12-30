# Learning Task Tracker - Product Requirements Document

> A Python-based learning task management system adapted from [beads](https://github.com/steveyegge/beads), designed to power AI tutoring agents at scale.

## 1. Vision & Goals

### 1.1 What We're Building

A **data tooling layer** that enables AI tutoring agents to:
- Guide learners through structured projects
- Track progress through hierarchical tasks
- Validate submissions (proof of work)
- Maintain context across sessions
- Facilitate pedagogically-aware conversations

### 1.2 What We're NOT Building (Yet)

- Agent logic, prompts, or LLM orchestration (LangGraph handles this)
- Session/conversation management (LangGraph manages thread_id automatically)
- Authentication/authorization (assume JWT with `learner_id`)
- File storage (submissions are text/code strings for now)
- Grading rubrics (simple pass/fail validation only)
- Redis caching or task queues (direct DB for now)

### 1.3 Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Stateless Agents** | All state in DB; agent loads context at runtime |
| **Type Safety** | Pydantic models for all data structures |
| **Scalable Foundation** | PostgreSQL, clean separation, easy to add queues later |
| **Two Interfaces** | Admin CLI (setup) + Agent Tools (runtime) |
| **Beads-Inspired** | Borrow proven patterns from beads codebase |

---

## 2. Architecture Overview

### 2.1 Two-Layer Architecture

> See [ADR-001](./adr/001-learner-scoped-task-progress.md) for detailed rationale.

This system implements a **Template + Instance** architecture that separates:
- **Template Layer**: Shared curriculum content (authored once, used by all learners)
- **Instance Layer**: Per-learner progress and work products

**Key Principle**: Any entity with both "definition" and "per-user state" aspects must be split into two layers. The template layer defines *what* learners work on. The instance layer tracks *how* each learner progresses.

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

### 2.2 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     LEARNING TASK TRACKER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐              ┌──────────────────┐         │
│  │   Admin CLI      │              │   Agent Tools    │         │
│  │   (Setup)        │              │   (Runtime)      │         │
│  │                  │              │                  │         │
│  │  • ingest        │              │  • get_ready     │         │
│  │  • create_project│              │  • show_task     │         │
│  │  • version       │              │  • start_task    │         │
│  │  • export        │              │  • submit        │         │
│  └────────┬─────────┘              │  • add_comment   │         │
│           │                        │  • get_context   │         │
│           │                        │  • go_back       │         │
│           │                        └────────┬─────────┘         │
│           │                                 │                    │
│           └────────────┬───────────────────┘                    │
│                        │                                         │
│                        ▼                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Service Layer                         │    │
│  │                                                          │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │    │
│  │  │ Task        │ │ Submission  │ │ Learning    │        │    │
│  │  │ Management  │ │ & Validation│ │ Objectives  │        │    │
│  │  └─────────────┘ └─────────────┘ └─────────────┘        │    │
│  │                                                          │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │    │
│  │  │ Dependency  │ │ Progress    │ │ Context     │        │    │
│  │  │ Resolution  │ │ Tracking    │ │ Loading     │        │    │
│  │  └─────────────┘ └─────────────┘ └─────────────┘        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                        │                                         │
│                        ▼                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Data Layer                            │    │
│  │            (Template + Instance Layers)                  │    │
│  │                                                          │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │              PostgreSQL Database                 │    │    │
│  │  │                                                  │    │    │
│  │  │  Template: tasks, dependencies, objectives       │    │    │
│  │  │  Instance: learner_task_progress, submissions    │    │    │
│  │  │            validations, status_summaries         │    │    │
│  │  │  Shared:   learners, content, events             │    │    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Concepts

### 3.1 Task Hierarchy

All work items share the same data model (like beads), differentiated by `task_type`:

```
Project (task_type: "project")
│
├── Epic (task_type: "epic")
│   │   "Build a FastAPI Backend"
│   │
│   ├── Task (task_type: "task")
│   │   │   "Create user endpoints"
│   │   │
│   │   ├── Subtask (task_type: "subtask")
│   │   │       "Create GET /users endpoint"
│   │   │
│   │   └── Subtask
│   │       │   "Create POST /users endpoint"
│   │       │
│   │       └── Subtask (unlimited nesting)
│   │               "Validate email format"
│   │
│   └── Task
│           "Create product endpoints"
│
└── Epic
        "Build a React Frontend"
```

**Key Properties:**
- Unlimited nesting depth via `parent_id`
- Hierarchical IDs: `proj-a1b2`, `proj-a1b2.1`, `proj-a1b2.1.1`
- Each level has: description, learning objectives, content refs
- Status propagates: parent can't close until children complete

### 3.2 Learning Context at Every Level

Each task carries both **project context** and **pedagogical context**:

```python
# Project Context (what we're building)
description: "Create a function that retrieves the homepage data"

# Pedagogical Context (what we're learning)
learning_objectives: [
    {
        "level": "apply",
        "description": "Apply list iteration to extract nested data"
    },
    {
        "level": "understand",
        "description": "Understand how FastAPI path operations work"
    }
]

# Content References (learning materials)
content_refs: ["content-abc123", "content-def456"]
# OR inline content
content: "To create a FastAPI endpoint, use the @app.get decorator..."
```

### 3.3 Submissions as Proof of Work

A **submission** is an atomic piece of evidence that a task was attempted:

```python
Submission(
    id="sub-xyz789",
    task_id="proj-a1b2.1.1",
    learner_id="learner-123",

    # The actual work product
    submission_type="code",  # code | sql | jupyter_cell | text | result_set
    content="def get_users(): return db.query(User).all()",

    # Metadata
    attempt_number=2,
    submitted_at=datetime(...)
)
```

### 3.4 Validation (Binary Pass/Fail)

Validation is simple: does the submission meet acceptance criteria?

```python
Validation(
    id="val-abc123",
    submission_id="sub-xyz789",
    task_id="proj-a1b2.1.1",

    passed=False,
    error_message="Function 'get_users' missing return type annotation",

    validated_at=datetime(...),
    validator_type="automated"  # automated | manual
)
```

**Subtasks**: Must pass validation to proceed (like unit tests)
**Tasks/Epics**: May receive feedback even if passing (architectural suggestions)

### 3.5 Context Loading

The agent is **stateless** - LangGraph manages the thread/session automatically.
At each interaction, we load context from the database:

1. Current task details + structured acceptance criteria
2. Learning objectives for this task
3. Submission history for this task
4. Status summaries (versioned history)
5. What's blocked vs. ready (in_progress tasks first)

**Note**: Session/conversation management is handled by LangGraph's thread_id mechanism, not by this system.

### 3.6 Dependencies (From Beads)

```python
Dependency(
    task_id="proj-a1b2.1.2",      # This task...
    depends_on_id="proj-a1b2.1.1", # ...depends on this one
    dependency_type="blocks"       # blocks | parent_child | related
)
```

**Dependency Types:**
| Type | Behavior |
|------|----------|
| `blocks` | Task cannot start until dependency is closed |
| `parent_child` | Hierarchical relationship (implicit via `parent_id`) |
| `related` | Informational link, no blocking |

---

## 4. Data Model Summary

> Full schemas in [01-data-models.md](./01-data-models.md)

### Core Entities

| Entity | Layer | Purpose | Key Fields |
|--------|-------|---------|------------|
| **Task** | Template | Work item definition (shared) | id, title, description, task_type, parent_id, acceptance_criteria, learning_objectives |
| **LearnerTaskProgress** | Instance | Per-learner status tracking | task_id, learner_id, status, started_at, completed_at |
| **Dependency** | Template | Relationships between tasks | task_id, depends_on_id, dependency_type |
| **LearningObjective** | Template | Pedagogical goals | taxonomy, level, description, task_id |
| **AcceptanceCriterion** | Template | Structured pass/fail criteria | task_id, criterion_type, description |
| **Submission** | Instance | Learner's proof of work | task_id, learner_id, content, submission_type, attempt_number |
| **Validation** | Instance | Pass/fail check on submission | submission_id, passed, error_message |
| **StatusSummary** | Instance | Versioned status updates | task_id, learner_id, summary, version, created_at |
| **Comment** | Dual | Task comments (shared or private) | task_id, learner_id (nullable), author, text |
| **Learner** | Shared | User profile | id, created_at, metadata |
| **Content** | Template | Learning materials | id, content_type, body |
| **Event** | Shared | Audit trail | entity_type, entity_id, event_type, actor, old_value, new_value |

### Status Workflow

```
                    ┌──────────────┐
                    │              │
           ┌───────►│   blocked    │◄───────┐
           │        │              │        │
           │        └──────────────┘        │
           │               │                │
           │               │ unblocked      │
           │               ▼                │
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │              │ │              │ │              │
    │    open      │►│ in_progress  │►│   closed     │
    │              │ │              │ │              │
    └──────────────┘ └──────────────┘ └──────────────┘
           ▲                                │
           │                                │
           └────────────────────────────────┘
                     reopen (go_back)
```

**Status Transition Rules:**
- `open → in_progress`: Always allowed
- `in_progress → blocked`: When dependency becomes incomplete
- `blocked → in_progress`: When all dependencies complete
- `in_progress → closed`: Requires passing validation (for subtasks)
- `closed → open`: Explicit "go_back" action

---

## 5. Module Breakdown

### 5.1 Task Management
> [02-task-management.md](./02-task-management.md)

**Responsibilities:**
- CRUD operations for tasks at all hierarchy levels
- Status transitions with validation rules
- Hierarchy traversal (get parent, get children, get ancestors)
- Comments and feedback attachment
- Automatic status propagation (parent blocked if child incomplete)

**Key Functions:**
```python
create_task(task: TaskCreate) -> Task
get_task(task_id: str) -> Task
update_task(task_id: str, updates: TaskUpdate) -> Task
update_status(task_id: str, new_status: Status, actor: str) -> Task
add_comment(task_id: str, comment: CommentCreate) -> Comment
get_children(task_id: str, recursive: bool = False) -> List[Task]
get_ancestors(task_id: str) -> List[Task]
```

### 5.2 Dependencies
> [03-dependencies.md](./03-dependencies.md)

**Responsibilities:**
- Add/remove dependency relationships
- Calculate ready work (unblocked tasks)
- Detect cycles (prevent circular dependencies)
- Propagate blocking through hierarchy

**Key Functions:**
```python
add_dependency(dep: DependencyCreate) -> Dependency
remove_dependency(task_id: str, depends_on_id: str) -> None
get_ready_work(learner_id: str, project_id: str) -> List[Task]
get_blocked_tasks(project_id: str) -> List[BlockedTask]
detect_cycles(project_id: str) -> List[List[str]]
is_task_ready(task_id: str) -> bool
```

### 5.3 Submissions & Validation
> [04-submissions-validation.md](./04-submissions-validation.md)

**Responsibilities:**
- Record submissions (proof of work)
- Trigger validation (for now: simple pass/fail)
- Track attempt history
- Gate status transitions on validation

**Key Functions:**
```python
create_submission(submission: SubmissionCreate) -> Submission
get_submissions(task_id: str, learner_id: str) -> List[Submission]
validate_submission(submission_id: str) -> Validation
get_latest_validation(task_id: str, learner_id: str) -> Validation | None
can_close_task(task_id: str, learner_id: str) -> tuple[bool, str]
```

**Validation Flow:**
```
Submission Created
        │
        ▼
┌───────────────────┐
│ Run Acceptance    │
│ Criteria Check    │
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
 PASSED      FAILED
    │           │
    ▼           ▼
 Can close   Return error
 task        message
```

### 5.4 Learning & Progress
> [05-learning-progress.md](./05-learning-progress.md)

**Responsibilities:**
- Attach learning objectives to tasks
- Track progress per learner (derived from validation results)
- Generate progress summaries
- Hierarchical summarization (compact completed work at any level)
- Content reference management

**Key Functions:**
```python
attach_objective(task_id: str, objective: ObjectiveCreate) -> LearningObjective
get_objectives(task_id: str) -> List[LearningObjective]
get_learner_progress(learner_id: str, project_id: str) -> ProgressSummary
summarize_completed(task_id: str, learner_id: str) -> StatusSummary  # Works for any task_type
attach_content(task_id: str, content_id: str) -> None
```

**Note**: Objective achievement is derived from successful validation, not tracked separately.

### 5.5 Context Loading

**Note**: Session and conversation management is handled by LangGraph's thread_id mechanism. This system only provides task context.

**Responsibilities:**
- Load task context for stateless agents
- Aggregate relevant data (hierarchy, objectives, validation history)
- Provide navigation info (ready work, blockers)

**Key Functions:**
```python
load_task_context(task_id: str, learner_id: str) -> TaskContext
get_task_hierarchy(task_id: str) -> List[Task]  # Ancestors up to project
```

**TaskContext Structure:**
```python
@dataclass
class TaskContext:
    # Current position
    current_task: Task  # Template data
    learner_status: str  # From learner_task_progress (open|in_progress|blocked|closed)
    task_ancestors: List[Task]  # [parent, grandparent, ..., project]

    # Task details
    learning_objectives: List[LearningObjective]
    acceptance_criteria: List[AcceptanceCriterion]
    task_content: str | None

    # History for this learner
    submissions: List[Submission]
    latest_validation: Validation | None
    status_summaries: List[StatusSummary]

    # Navigation
    ready_tasks: List[Task]     # in_progress first, then open (joins learner_task_progress)
    blocked_by: List[Task]      # What's blocking current task
    children: List[Task]        # Child tasks
```

### 5.6 Agent Tools (Runtime CLI)
> [07-agent-tools.md](./07-agent-tools.md)

**Responsibilities:**
- Expose stateless functions for LLM agents
- Accept structured arguments, return structured responses
- Handle errors gracefully with informative messages
- All operations scoped to learner

**Tool Definitions:**
```python
# Navigation
get_ready(project_id: str) -> List[TaskSummary]  # Returns in_progress first, then open
show_task(task_id: str) -> TaskDetail
get_context(task_id: str, learner_id: str) -> TaskContext

# Progress
start_task(task_id: str, learner_id: str) -> TaskContext  # Sets status to in_progress + loads full context
submit(task_id: str, learner_id: str, content: str, submission_type: str) -> SubmissionResult

# Feedback
add_comment(task_id: str, comment: str, author: str) -> Comment
get_comments(task_id: str) -> List[Comment]

# Navigation
go_back(task_id: str, reason: str) -> Task  # Reopen a closed task, reason required
request_help(task_id: str, message: str) -> HelpRequest
```

### 5.7 Admin CLI (Project Setup)
> [08-admin-cli.md](./08-admin-cli.md)

**Responsibilities:**
- Ingest project structures (JSONL/JSON)
- Create/update/version projects
- Export projects for backup/sharing
- Bulk operations

**Commands:**
```bash
# Project management
ltt project create --title "Build E-commerce Site" --description "..."
ltt project list
ltt project export <project_id> --format jsonl

# Ingestion
ltt ingest <file.jsonl> --project <project_id>
ltt ingest <file.jsonl> --create-project

# Versioning
ltt project version <project_id> --tag "v1.0"
ltt project checkout <project_id> --version "v1.0"

# Content
ltt content create --type markdown --body "..."
ltt content attach <content_id> <task_id>
```

---

## 6. Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Language** | Python 3.12+ | Team expertise, AI ecosystem |
| **Type Safety** | Pydantic v2 | Validation, serialization, schema generation |
| **Database** | PostgreSQL 15+ | Scalable, JSON support, recursive CTEs |
| **ORM** | SQLAlchemy 2.0 | Async support, type hints, mature |
| **CLI** | Typer | Pydantic integration, auto-docs |
| **API** | FastAPI | OpenAPI, async, Pydantic native |
| **Testing** | pytest + pytest-asyncio | Standard, async support |
| **Migrations** | Alembic | SQLAlchemy integration |

### Future Additions (Not Now)
- **Redis**: Session caching, rate limiting
- **Celery/Dramatiq**: Background validation, summarization
- **S3/GCS**: File submissions, exports

---

## 7. Database Schema Overview

> Full DDL in [01-data-models.md](./01-data-models.md)

```sql
-- Template Layer: Core task hierarchy (inspired by beads.issues)
CREATE TABLE tasks (
    id VARCHAR PRIMARY KEY,           -- Hierarchical: proj-a1b2.1.1
    parent_id VARCHAR REFERENCES tasks(id),
    project_id VARCHAR NOT NULL,      -- Root project ID

    title VARCHAR(500) NOT NULL,
    description TEXT DEFAULT '',
    acceptance_criteria TEXT DEFAULT '',
    notes TEXT DEFAULT '',

    task_type VARCHAR DEFAULT 'task', -- project|epic|task|subtask
    priority INTEGER DEFAULT 2,       -- 0-4

    content TEXT,                     -- Inline content (learning materials)
    content_refs VARCHAR[],           -- References to content table

    -- Versioning
    version INTEGER DEFAULT 1,
    version_tag VARCHAR,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()

    -- NO status - moved to learner_task_progress
    -- NO closed_at - moved to learner_task_progress
    -- NO close_reason - moved to learner_task_progress
);

-- Instance Layer: Per-learner task status
CREATE TABLE learner_task_progress (
    id VARCHAR PRIMARY KEY,
    task_id VARCHAR REFERENCES tasks(id) ON DELETE CASCADE NOT NULL,
    learner_id VARCHAR REFERENCES learners(id) ON DELETE CASCADE NOT NULL,

    status VARCHAR NOT NULL DEFAULT 'open',  -- open|in_progress|blocked|closed
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    close_reason TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(task_id, learner_id)
);

-- Dependencies (inspired by beads.dependencies)
CREATE TABLE dependencies (
    task_id VARCHAR REFERENCES tasks(id),
    depends_on_id VARCHAR REFERENCES tasks(id),
    dependency_type VARCHAR DEFAULT 'blocks',
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (task_id, depends_on_id)
);

-- Learning objectives (new for learning platform)
CREATE TABLE learning_objectives (
    id VARCHAR PRIMARY KEY,
    task_id VARCHAR REFERENCES tasks(id),
    taxonomy VARCHAR DEFAULT 'bloom',  -- bloom|custom
    level VARCHAR,                     -- remember|understand|apply|analyze|evaluate|create
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Learner profiles (new for learning platform)
CREATE TABLE learners (
    id VARCHAR PRIMARY KEY,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Submissions (new for learning platform)
CREATE TABLE submissions (
    id VARCHAR PRIMARY KEY,
    task_id VARCHAR REFERENCES tasks(id),
    learner_id VARCHAR REFERENCES learners(id),

    submission_type VARCHAR NOT NULL,  -- code|sql|jupyter_cell|text|result_set
    content TEXT NOT NULL,
    attempt_number INTEGER DEFAULT 1,

    submitted_at TIMESTAMP DEFAULT NOW()
);

-- Validations (simplified from beads.validations)
CREATE TABLE validations (
    id VARCHAR PRIMARY KEY,
    submission_id VARCHAR REFERENCES submissions(id),
    task_id VARCHAR REFERENCES tasks(id),

    passed BOOLEAN NOT NULL,
    error_message TEXT,

    validator_type VARCHAR DEFAULT 'automated',
    validated_at TIMESTAMP DEFAULT NOW()
);

-- Acceptance criteria (structured validation rules)
CREATE TABLE acceptance_criteria (
    id VARCHAR PRIMARY KEY,
    task_id VARCHAR REFERENCES tasks(id),
    criterion_type VARCHAR NOT NULL,   -- code_test|sql_result|text_match|manual
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Status summaries (versioned progress notes)
CREATE TABLE status_summaries (
    id VARCHAR PRIMARY KEY,
    task_id VARCHAR REFERENCES tasks(id),
    learner_id VARCHAR REFERENCES learners(id),

    summary TEXT NOT NULL,
    version INTEGER DEFAULT 1,

    created_at TIMESTAMP DEFAULT NOW()
);

-- Content library (new for learning platform)
CREATE TABLE content (
    id VARCHAR PRIMARY KEY,
    content_type VARCHAR NOT NULL,     -- markdown|code|video_ref|external_link
    body TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Comments (from beads) - Dual-purpose: shared or per-learner
CREATE TABLE comments (
    id VARCHAR PRIMARY KEY,
    task_id VARCHAR REFERENCES tasks(id) ON DELETE CASCADE NOT NULL,
    learner_id VARCHAR REFERENCES learners(id) ON DELETE CASCADE,  -- NULL = shared, set = private
    author VARCHAR NOT NULL,           -- learner_id or 'system' or 'tutor'
    text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit trail (from beads.events)
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR NOT NULL,      -- task|submission|session|...
    entity_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,       -- created|updated|status_changed|...
    actor VARCHAR NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_tasks_parent ON tasks(parent_id);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_learner_task_progress_task_learner ON learner_task_progress(task_id, learner_id);
CREATE INDEX idx_learner_task_progress_learner_status ON learner_task_progress(learner_id, status);
CREATE INDEX idx_deps_task ON dependencies(task_id);
CREATE INDEX idx_deps_depends_on ON dependencies(depends_on_id);
CREATE INDEX idx_submissions_task_learner ON submissions(task_id, learner_id);
CREATE INDEX idx_acceptance_criteria_task ON acceptance_criteria(task_id);
CREATE INDEX idx_status_summaries_task_learner ON status_summaries(task_id, learner_id);
CREATE INDEX idx_comments_task_learner ON comments(task_id, learner_id);
CREATE INDEX idx_events_entity ON events(entity_type, entity_id);
```

---

## 8. Key Algorithms (From Beads)

### 8.1 Ready Work Detection

Adapted from [beads/internal/storage/sqlite/ready.go](../internal/storage/sqlite/ready.go) to use learner_task_progress:

```sql
-- Tasks that are unblocked and ready to work on FOR A SPECIFIC LEARNER
-- Priority: in_progress first, then open
-- This query joins template (tasks) with instance (learner_task_progress)
WITH RECURSIVE
  blocked_directly AS (
    SELECT DISTINCT d.task_id
    FROM dependencies d
    LEFT JOIN learner_task_progress ltp_blocker
      ON ltp_blocker.task_id = d.depends_on_id
      AND ltp_blocker.learner_id = :learner_id
    WHERE d.dependency_type = 'blocks'
      -- If no progress record, default to 'open' (not closed)
      AND COALESCE(ltp_blocker.status, 'open') IN ('open', 'in_progress', 'blocked')
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
  COALESCE(ltp.status, 'open') as learner_status,
  ltp.started_at,
  ltp.completed_at
FROM tasks t
LEFT JOIN learner_task_progress ltp
  ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
WHERE COALESCE(ltp.status, 'open') IN ('in_progress', 'open')
  AND t.project_id = :project_id
  AND NOT EXISTS (SELECT 1 FROM blocked_transitively WHERE task_id = t.id)
ORDER BY
  CASE COALESCE(ltp.status, 'open')
    WHEN 'in_progress' THEN 0
    WHEN 'open' THEN 1
  END,
  t.priority,
  t.created_at;
```

**Key Changes from Beads**:
- Joins `learner_task_progress` for per-learner status
- Uses `COALESCE(ltp.status, 'open')` for lazy initialization (no record = open)
- Scoped by `learner_id` parameter
- Checks blocker status from learner's perspective

### 8.2 Hierarchical ID Generation

From [beads/internal/storage/sqlite/ids.go](../internal/storage/sqlite/ids.go):

```python
def generate_task_id(parent_id: str | None, project_prefix: str) -> str:
    if parent_id is None:
        # Root task: generate hash-based ID
        hash_part = hashlib.sha256(uuid4().bytes).hexdigest()[:4]
        return f"{project_prefix}-{hash_part}"
    else:
        # Child task: increment counter
        last_child = get_last_child_number(parent_id)
        return f"{parent_id}.{last_child + 1}"

# Examples:
# Project: "proj-a1b2"
# Epic:    "proj-a1b2.1"
# Task:    "proj-a1b2.1.1"
# Subtask: "proj-a1b2.1.1.1"
```

### 8.3 Status Transition Validation

```python
VALID_TRANSITIONS = {
    'open': ['in_progress', 'blocked'],
    'in_progress': ['open', 'blocked', 'closed'],
    'blocked': ['open', 'in_progress'],
    'closed': ['open'],  # Only via explicit "go_back"
}

def validate_status_transition(
    task: Task,
    current_status: Status,  # From learner_task_progress (or 'open' if no record)
    new_status: Status,
    learner_id: str
) -> tuple[bool, str]:
    # Check transition is valid
    if new_status not in VALID_TRANSITIONS[current_status]:
        return False, f"Cannot transition from {current_status} to {new_status}"

    # Check closing requirements
    if new_status == 'closed':
        if task.task_type == 'subtask':
            # Subtasks require passing validation
            validation = get_latest_validation(task.id, learner_id)
            if not validation or not validation.passed:
                return False, "Subtask requires passing validation before closing"

        # Check all children are closed FOR THIS LEARNER
        # Query children with LEFT JOIN on learner_task_progress
        open_children = get_children_with_status(task.id, learner_id, status_not='closed')
        if open_children:
            return False, f"Cannot close: {len(open_children)} children still open"

    return True, ""

def get_or_create_progress(
    db, task_id: str, learner_id: str
) -> LearnerTaskProgress:
    """Lazy initialization: create progress record on first access."""
    progress = db.query(LearnerTaskProgress).filter_by(
        task_id=task_id,
        learner_id=learner_id
    ).first()

    if progress:
        return progress

    # Create with default status='open'
    new_progress = LearnerTaskProgress(
        id=generate_entity_id("ltp"),
        task_id=task_id,
        learner_id=learner_id,
        status="open"
    )
    db.add(new_progress)
    db.commit()
    return new_progress
```

---

## 9. Module Documentation

Each module has its own detailed specification:

| Document | Description |
|----------|-------------|
| [01-data-models.md](./01-data-models.md) | Complete Pydantic schemas and DB models |
| [02-task-management.md](./02-task-management.md) | Task CRUD, hierarchy, status transitions |
| [03-dependencies.md](./03-dependencies.md) | Dependency management, blocking, ready work |
| [04-submissions-validation.md](./04-submissions-validation.md) | Submissions, validation, attempt tracking |
| [05-learning-progress.md](./05-learning-progress.md) | Objectives, progress, summarization |
| [07-agent-tools.md](./07-agent-tools.md) | Runtime tools for LLM agents |
| [08-admin-cli.md](./08-admin-cli.md) | Project setup and ingestion |

**Architecture Decisions:**
| Document | Description |
|----------|-------------|
| [ADR-001: Two-Layer Architecture](./adr/001-learner-scoped-task-progress.md) | Template + Instance pattern for multi-learner support |

**Note**: Session/conversation management is handled by LangGraph. See section 5.5 for context loading.

---

## 10. Reference: Beads Codebase

Key files to reference when implementing:

| Feature | Beads File | Notes |
|---------|------------|-------|
| Data models | `internal/types/types.go` | Issue, Dependency, Status, etc. |
| Storage interface | `internal/storage/storage.go` | Clean abstraction over DB |
| SQLite schema | `internal/storage/sqlite/schema.go` | Table definitions |
| Ready work | `internal/storage/sqlite/ready.go` | Unblocked task detection |
| Status validation | `internal/storage/sqlite/validators.go` | Transition rules |
| ID generation | `internal/storage/sqlite/ids.go` | Hash + hierarchical IDs |
| Dependencies | `internal/storage/sqlite/dependencies.go` | Blocking logic |
| Events/audit | `internal/storage/sqlite/events.go` | Audit trail |

---

## 11. Success Criteria

The implementation is complete when:

1. **Data Layer**
   - [ ] All Pydantic models defined with validation
   - [ ] SQLAlchemy models match Pydantic
   - [ ] Database migrations/init work
   - [ ] CRUD operations pass tests

2. **Task Management**
   - [ ] Hierarchical tasks can be created - with protection, epic needs project, task needs epic, subtask needs task, subtask(3) needs subtask(2)
   - [ ] Status transitions enforce rules
   - [ ] Children block parent closure
   - [ ] Comments can be attached

3. **Dependencies**
   - [ ] Blocking relationships enforced
   - [ ] Ready work correctly calculated
   - [ ] Cycle detection works
   - [ ] No orphaned dependencies

4. **Submissions & Validation**
   - [ ] Submissions can be recorded
   - [ ] Validation runs on submission
   - [ ] Status gated on validation (subtasks)
   - [ ] Attempt history tracked

5. **Learning**
   - [ ] Objectives attach to tasks
   - [ ] Progress tracked per learner
   - [ ] Summarization generates text for any task_type
   - [ ] Status summaries versioned correctly

6. **CLIs**
   - [ ] Agent tools can work as functions/cli
   - [ ] Admin CLI can ingest projects
   - [ ] Context loading returns full task context

---

## 12. Out of Scope (Future Work)

Explicitly deferred:
- Authentication/authorization system
- File upload for submissions
- Grading rubrics and scoring
- Redis caching layer
- Background task queues
- Multi-tenancy
- Real-time notifications
- Analytics dashboard
- LLM agent implementation
