# LTT Core Engine

> The core Learning Task Tracker engine — models, services, tools, CLI, and migrations.

---

## What This Is

LTT Core is the domain layer of the Learning Task Tracker. It owns:

- **Data models** (Pydantic + SQLAlchemy) for tasks, learners, submissions, objectives
- **Service layer** — business logic for task management, progress, dependencies, validation
- **Agent tools** — stateless interface for LLM tutoring agents
- **Admin CLI** — project creation, ingestion, learner management
- **Migrations** — Alembic schema management for PostgreSQL

Everything else (API server, frontend, AI agent) depends on this package.

---

## Architecture

### Two-Layer Design ([ADR-001](../../docs/adr/001-learner-scoped-task-progress.md))

**Template Layer** (shared curriculum):
- `tasks` — hierarchical work items (project/epic/task/subtask)
- `learning_objectives` — Bloom's taxonomy objectives
- `dependencies` — blocking relationships between tasks
- `content` — learning materials

**Instance Layer** (per-learner state):
- `learner_task_progress` — status (open/in_progress/blocked/closed)
- `submissions` — proof of work
- `validations` — pass/fail results
- `status_summaries` — progress notes

1,000 learners share the same project definition with independent progress.

---

## Directory Layout

```
src/ltt/
├── models/                  # Data models
│   ├── task.py              #   Task, TaskCreate, TaskUpdate, TaskModel
│   ├── learner_task_progress.py  #   Per-learner status
│   ├── submission.py        #   Submissions + Validation
│   ├── dependency.py        #   Blocking relationships
│   ├── learning.py          #   Learning objectives
│   ├── content.py           #   Learning materials
│   ├── learner.py           #   Learner profiles
│   ├── comment.py           #   Task comments
│   ├── event.py             #   Audit trail
│   ├── lti_mapping.py       #   LTI user → LTT learner
│   ├── lti_launch.py        #   LTI launch persistence
│   └── base.py              #   SQLAlchemy base
│
├── services/                # Business logic
│   ├── task_service.py      #   CRUD, hierarchy traversal
│   ├── progress_service.py  #   Status transitions, start/close/reopen
│   ├── dependency_service.py #  Ready work, blocking, cycle detection
│   ├── submission_service.py #  Create submissions, attempt tracking
│   ├── validation_service.py #  Validate submissions, closure gates
│   ├── ingest.py            #   Import projects from JSON
│   ├── export.py            #   Export to JSON/JSONL
│   ├── learning/            #   Objectives, progress, Bloom distribution
│   └── validators/          #   Pluggable validation (SimpleValidator)
│
├── tools/                   # Agent runtime interface
│   ├── navigation.py        #   get_ready, show_task, get_context
│   ├── progress.py          #   start_task, submit (auto-close on pass)
│   ├── feedback.py          #   add_comment, get_comments
│   ├── control.py           #   go_back, request_help
│   └── schemas.py           #   Tool registry for MCP/function calling
│
├── cli/                     # Admin CLI (Typer)
│   └── main.py              #   project, task, content, learner, db commands
│
├── db/
│   └── migrations/          # Alembic migrations
│
└── utils/
    └── ids.py               # Hierarchical ID generation
```

---

## Key Patterns

### Status is per-learner, not per-task

Tasks are templates. Status lives in `learner_task_progress`:

```python
# Correct
progress = await get_or_create_progress(session, task_id, learner_id)
if progress.status == "closed": ...

# Wrong — Task has no status field
task = await get_task(session, task_id)
task.status  # AttributeError
```

### Lazy initialization

Progress records are created on first access:

```python
progress = await get_or_create_progress(session, task_id, learner_id)
# Creates record with status='open' if it doesn't exist
```

### Submission-driven completion ([ADR-002](../../docs/adr/002-submission-driven-task-completion.md))

```
submit() → validate → pass? → close_task() → try_auto_close_ancestors()
```

Subtasks require passing validation to close. Parent tasks/epics auto-close when all children complete.

### Hierarchical IDs

```
proj-a1b2         # project
proj-a1b2.1       # epic
proj-a1b2.1.1     # task
proj-a1b2.1.1.1   # subtask
```

---

## Usage

### Agent Tools (for LLM agents)

```python
from ltt.tools import execute_tool, get_tool_schemas

schemas = get_tool_schemas()  # OpenAI-compatible function schemas

result = await execute_tool(
    "get_ready",
    {"project_id": "proj-123"},
    learner_id="learner-456",
    session=session
)
```

Available tools: `get_ready`, `show_task`, `get_context`, `start_task`, `submit`, `add_comment`, `get_comments`, `go_back`, `request_help`

### Admin CLI

```bash
# Project management
python -m ltt.cli.main project create "My Project"
python -m ltt.cli.main project list
python -m ltt.cli.main ingest project project.json --dry-run
python -m ltt.cli.main ingest project project.json

# Learner progress
python -m ltt.cli.main learner progress learner-abc123 proj-xyz789
```

### Service Layer (direct Python API)

```python
from ltt.services.task_service import create_task, get_task, get_children
from ltt.services.progress_service import get_or_create_progress, update_status
from ltt.services.dependency_service import get_ready_work
from ltt.services.submission_service import create_submission
```

See [CLAUDE.md](../../CLAUDE.md) for the full service API reference.

---

## Development

### Running Tests

```bash
uv run pytest services/ltt-core/tests/ -v        # all (167 tests)
uv run pytest services/ltt-core/tests/ -q         # fast/quiet

# By module
uv run pytest services/ltt-core/tests/services/test_task_service.py -v
uv run pytest services/ltt-core/tests/services/test_dependency_service.py -v
uv run pytest services/ltt-core/tests/tools/ -v
```

### Migrations

```bash
# Run
PYTHONPATH=services/ltt-core/src uv run --package ltt-core python -m alembic upgrade head

# Create
PYTHONPATH=services/ltt-core/src uv run --package ltt-core python -m alembic revision --autogenerate -m "description"

# Rollback
PYTHONPATH=services/ltt-core/src uv run --package ltt-core python -m alembic downgrade -1
```

### Dependencies

```
pydantic>=2.0, sqlalchemy[asyncio]>=2.0, asyncpg, alembic, typer, rich
```

---

## Related Docs

- [CLAUDE.md](../../CLAUDE.md) — Full API reference (models, services, tools, patterns)
- [ADR-001](../../docs/adr/001-learner-scoped-task-progress.md) — Two-layer architecture
- [ADR-002](../../docs/adr/002-submission-driven-task-completion.md) — Submission-driven completion
- [Project ingestion schema](../../docs/schema/project-ingestion.md) — JSON format for project import
