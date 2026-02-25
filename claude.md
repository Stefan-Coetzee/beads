# Learning Task Tracker (LTT) - Developer Reference

> Quick reference for developers and LLMs working with the LTT codebase.

---

## Architecture Overview

### Two-Layer Architecture (ADR-001)

LTT separates **curriculum** (what to learn) from **progress** (learner-specific state):

**Template Layer** (shared across all learners):
- `tasks` table - Project structure, descriptions, acceptance criteria
- `learning_objectives` - Bloom's taxonomy objectives
- `dependencies` - Task relationships and blocking
- `content` - Learning materials

**Instance Layer** (per-learner):
- `learner_task_progress` - Status (open/in_progress/blocked/closed)
- `submissions` - Learner's work submissions
- `validations` - Pass/fail results
- `status_summaries` - Progress notes

**Key Insight**: 1,000 learners can work on the same project with independent progress tracking.

### LTI 1.3 Access Model

**LTI is the only entry point for learners.** There is no standalone mode. Every session starts from Open edX via LTI 1.3.

```
Open edX → POST /lti/login → OIDC redirect → POST /lti/launch → JWT validation
  → map LTI user to LTT learner → persist launch → 302 to /workspace/{project_id}
```

Key components:
- `services/api-server/src/api/lti/` — All LTI backend code (adapter, config, storage, routes, users, grades, middleware)
- `configs/lti/` — Platform config (`platform.json`), RSA keys (`private.key`, `public.key`)
- `apps/web/src/lib/lti.ts` — Frontend LTI context (sessionStorage, iframe detection)
- `lti_user_mappings` table — Maps `(lti_sub, lti_iss)` to `learner_id`
- `lti_launches` table — Persists active launches for grade passback
- Redis — Caches launch data, nonces, state (TTL-based)

**Environment**: `LTT_REDIS_URL` must be set for LTI to work. If unset, LTI endpoints are disabled.

**Documentation**: See `docs/lti/` for full spec, architecture, and production checklist. See `docs/lti/cleanup/` for code that must be removed before production.

### Status State Machine

```
     ┌──────────┐
     │ blocked  │←────┐
     └────┬─────┘     │
          ▼           │
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │   open   │─→│in_progress│─→│ closed   │
  └──────────┘  └──────────┘  └────┬─────┘
       ▲                           │
       └───────────────────────────┘
              go_back (reopen)
```

---

## Repository Structure

Each major directory has its own README with setup instructions and details.

```
beadslocal/
├── services/                    # Backend services (Python)
│   ├── ltt-core/               # Core Learning Task Tracker engine (→ README.md)
│   │   ├── src/ltt/
│   │   │   ├── models/         # Pydantic + SQLAlchemy models
│   │   │   ├── services/       # Business logic layer
│   │   │   ├── tools/          # Agent runtime interface
│   │   │   ├── cli/            # Admin CLI (Typer)
│   │   │   ├── db/             # Database & migrations
│   │   │   └── utils/          # Utilities
│   │   ├── tests/              # ltt-core tests
│   │   └── pyproject.toml
│   │
│   ├── api-server/             # FastAPI REST API (→ README.md)
│   │   ├── src/api/
│   │   │   ├── lti/            # LTI 1.3 integration
│   │   │   │   ├── adapter.py  # PyLTI1p3 FastAPI adapter
│   │   │   │   ├── config.py   # Platform config loader
│   │   │   │   ├── storage.py  # Redis launch data storage
│   │   │   │   ├── routes.py   # /lti/login, /lti/launch, /lti/jwks
│   │   │   │   ├── users.py    # LTI user → LTT learner mapping
│   │   │   │   ├── grades.py   # AGS grade passback
│   │   │   │   └── middleware.py # LTI context resolution
│   │   │   └── ...
│   │   ├── tests/
│   │   └── pyproject.toml
│   │
│   └── agent-tutor/            # LLM tutoring agent (→ src/agent/README.md)
│       ├── src/agent/
│       ├── tests/
│       └── pyproject.toml
│
├── apps/
│   └── web/                    # Next.js frontend (→ README.md)
│       ├── src/
│       ├── package.json
│       └── README.md
│
├── infrastructure/             # (→ README.md)
│   ├── docker/
│   │   └── docker-compose.yml
│   └── terraform/
│
├── configs/
│   └── lti/                    # LTI 1.3 configuration
│       ├── platform.json       # Platform registration (issuer, client_id, endpoints)
│       ├── private.key         # RSA private key (gitignored)
│       └── public.key          # RSA public key
│
├── content/                    # (→ README.md)
│   └── projects/               # Project JSON files
│
├── tools/
│   ├── scripts/                # Dev utilities
│   └── simulation/             # Learner simulation
│
├── docs/
│   ├── lti/                    # LTI 1.3 spec & implementation docs
│   │   ├── cleanup/            # Code to remove for production
│   │   └── *.md                # Protocol, implementation, config, testing
│   ├── adr/                    # Architecture Decision Records
│   └── schema/
│
├── archive/                    # Historical code (not active)
│
├── .github/
│   └── workflows/              # CI/CD
│
├── pyproject.toml              # Workspace root (uv workspaces)
├── alembic.ini
├── docker-compose.yml          # Symlink to infrastructure/docker/
├── README.md
├── CLAUDE.md
└── LICENSE
```

---

## CLI Commands

**Note**: Run as `python -m ltt.cli.main <command>` or install as package for `ltt <command>`.

### Project Management

```bash
# Create new project
python -m ltt.cli.main project create "My Project" --description "Description"

# List all projects
python -m ltt.cli.main project list --limit 20

# Show project details
python -m ltt.cli.main project show proj-abc123

# Export project to JSON
python -m ltt.cli.main project export proj-abc123 --output backup.json --format json
```

### Project Ingestion

```bash
# Validate JSON structure (dry run - no changes)
python -m ltt.cli.main ingest project my_project.json --dry-run

# Import project from JSON
python -m ltt.cli.main ingest project my_project.json
```

**Input Format**: See [docs/schema/project-ingestion.md](docs/schema/project-ingestion.md)

### Task Management

```bash
# Create task under parent
python -m ltt.cli.main task create "Task Title" \
  --parent proj-abc123.1 \
  --description "Task description" \
  --ac "- Criterion 1\n- Criterion 2" \
  --type task \
  --priority 2

# Add learning objective to task
python -m ltt.cli.main task add-objective proj-abc123.1 \
  "Implement REST endpoints in FastAPI" \
  --level apply
```

**Task Types**: `project`, `epic`, `task`, `subtask`
**Bloom Levels**: `remember`, `understand`, `apply`, `analyze`, `evaluate`, `create`

### Content Management

```bash
# Create content from string
python -m ltt.cli.main content create \
  --type markdown \
  --body "# Tutorial Content"

# Create content from file
python -m ltt.cli.main content create \
  --type markdown \
  --file path/to/tutorial.md

# Attach content to task
python -m ltt.cli.main content attach cnt-xyz123 proj-abc123.1
```

**Content Types**: `markdown`, `code`, `video_ref`, `external_link`

### Learner Management

```bash
# Create learner
python -m ltt.cli.main learner create --metadata '{"name": "Alice"}'

# List learners
python -m ltt.cli.main learner list --limit 50

# Show learner progress in project
python -m ltt.cli.main learner progress learner-abc123 proj-xyz789
```

**Progress Output**:
```
Completed: 15/42
Percentage: 35.7%
In Progress: 3
Blocked: 2
Objectives: 8/18
```

### Database Operations

```bash
# Initialize database (run migrations)
python -m ltt.cli.main db init
```

**Direct Alembic** (alternative):
```bash
# Run migrations
PYTHONPATH=services/ltt-core/src uv run alembic upgrade head

# Create new migration
PYTHONPATH=services/ltt-core/src uv run alembic revision --autogenerate -m "Description"

# Rollback
PYTHONPATH=services/ltt-core/src uv run alembic downgrade -1
```

---

## Development Workflows

### Starting the LTI Dev Environment

```bash
# Option 1: Convenience script
./tools/scripts/start-lti-dev.sh

# Option 2: Manual (each in a separate terminal)
docker compose up -d postgres redis
PYTHONPATH=services/ltt-core/src uv run --package ltt-core python -m alembic upgrade head
LTT_REDIS_URL=redis://localhost:6379/0 uv run uvicorn api.app:app --host 0.0.0.0 --port 8000 --app-dir services/api-server/src --reload
cd apps/web && npm run dev
cloudflared tunnel --url http://localhost:3000  # free tunnel, random URL
```

### Running Tests

```bash
# All backend tests (Python — ltt-core + api-server + agent-tutor)
uv run pytest -v

# Specific backend service
uv run pytest services/ltt-core/tests/ -v
uv run pytest services/api-server/tests/ -v
uv run pytest services/agent-tutor/tests/ -v

# Specific module
uv run pytest services/ltt-core/tests/services/test_task_service.py -v
uv run pytest services/ltt-core/tests/tools/ -v

# With coverage
uv run pytest --cov=services --cov-report=term-missing

# Fast (quiet mode)
uv run pytest -q

# Frontend tests (Vitest + React Testing Library)
# IMPORTANT: Must run from apps/web/ — vitest.config.ts (jsdom, @/ alias,
# setup file) lives there. Running from the repo root will fail.
cd apps/web && npm test            # Single run
cd apps/web && npm run test:watch  # Watch mode
```

### Code Quality

```bash
# Lint and format
uv run ruff check services/ tools/
uv run ruff format services/ tools/

# Auto-fix issues
uv run ruff check --fix services/ tools/
```

### Database Management

```bash
# Start PostgreSQL (Docker)
docker-compose up -d

# Check status
docker-compose ps

# Stop
docker-compose down

# View logs
docker-compose logs -f postgres
```

---

## Key Concepts

### Hierarchical Task Structure

```
Project (proj-a1b2)
  ├── Epic (proj-a1b2.1)
  │   ├── Task (proj-a1b2.1.1)
  │   │   ├── Subtask (proj-a1b2.1.1.1)
  │   │   └── Subtask (proj-a1b2.1.1.2)
  │   └── Task (proj-a1b2.1.2)
  └── Epic (proj-a1b2.2)
```

- **Unlimited nesting** via `parent_id`
- **Hierarchical IDs** auto-generated
- **Context distribution**: Broad (project) → Specific (subtask)

### Dependency Types

**BLOCKS**: Hard dependency (Task B waits for Task A to close)
```python
await add_dependency(session, task_b.id, task_a.id, DependencyType.BLOCKS)
```

**PARENT_CHILD**: Implicit hierarchy (parent can't close until children close)
- Created automatically via `parent_id`

**RELATED**: Informational link (no blocking)

**Dependencies are unconstrained**: Can cross epics, can be between any task types.

### Learning Objectives (Bloom's Taxonomy)

```json
{
  "level": "apply",
  "description": "Implement JWT authentication in FastAPI"
}
```

**Levels** (low → high cognitive complexity):
1. `remember` - Recall facts, syntax
2. `understand` - Explain concepts
3. `apply` - Use knowledge (most common for implementation)
4. `analyze` - Break down, examine
5. `evaluate` - Judge, critique, compare
6. `create` - Build something new

**Achievement**: Derived from passing validations (not stored separately).

### Pedagogical Guidance Fields

**`tutor_guidance`** (Task/Subtask level):
```json
{
  "teaching_approach": "Start with real-world context before SQL",
  "discussion_prompts": ["What does 500 minutes mean in real life?"],
  "common_mistakes": ["Using = instead of >"],
  "hints_to_give": ["Try SHOW TABLES first", "Check column names"],
  "answer_rationale": "Explains WHY the answer works"
}
```

**`narrative_context`** (Project level):
```
"This data comes from President Naledi's water quality initiative.
You are helping analyze survey data that will impact real communities..."
```

These guide **HOW** LLM tutors teach, not just **WHAT**.

### Validation & Submissions

**Submission Types**: `code`, `sql`, `text`, `jupyter_cell`, `result_set`

**Validation Rules**:
- **Subtasks**: MUST have passing validation to close
- **Tasks/Epics**: Can close without validation (optional feedback)

**Current Validator**: SimpleValidator (non-empty check only)

---

## Agent Tools (Python API)

Stateless interface for LLM agents:

### Navigation Tools

```python
from ltt.tools import get_ready, show_task, get_context

# Get unblocked tasks (in_progress first, then open)
result = await get_ready(
    GetReadyInput(project_id="proj-123", task_type="task", limit=5),
    learner_id="learner-456",
    session
)

# Show detailed task info
result = await show_task(
    ShowTaskInput(task_id="proj-123.1.1"),
    learner_id="learner-456",
    session
)

# Get full context for task
result = await get_context(
    GetContextInput(task_id="proj-123.1.1"),
    learner_id="learner-456",
    session
)
```

### Progress Tools

```python
from ltt.tools import start_task, submit

# Start working on task (sets status to in_progress)
result = await start_task(
    StartTaskInput(task_id="proj-123.1.1"),
    learner_id="learner-456",
    session
)

# Submit work and trigger validation
result = await submit(
    SubmitInput(
        task_id="proj-123.1.1",
        content="def hello(): return 'world'",
        submission_type="code"
    ),
    learner_id="learner-456",
    session
)
```

### Feedback & Control Tools

```python
from ltt.tools import add_comment, get_comments, go_back, request_help

# Add comment
result = await add_comment(
    AddCommentInput(task_id="proj-123.1", comment="Question about this task"),
    learner_id="learner-456",
    session
)

# Get comments (shared + learner's private)
result = await get_comments(
    GetCommentsInput(task_id="proj-123.1", limit=10),
    learner_id="learner-456",
    session
)

# Reopen closed task
result = await go_back(
    GoBackInput(task_id="proj-123.1", reason="Need to revise approach"),
    learner_id="learner-456",
    session
)

# Request help
result = await request_help(
    RequestHelpInput(task_id="proj-123.1", message="Stuck on validation error"),
    learner_id="learner-456",
    session
)
```

### Tool Registry (for MCP/function calling)

```python
from ltt.tools import get_tool_schemas, execute_tool

# Get OpenAI-compatible schemas
schemas = get_tool_schemas()

# Execute tool by name
result = await execute_tool(
    "get_ready",
    {"project_id": "proj-123", "limit": 5},
    learner_id="learner-456",
    session
)
```

---

## Service Layer (Direct Access)

### Task Service

```python
from ltt.services.task_service import (
    create_task, get_task, update_task, delete_task,
    get_children, get_ancestors, add_comment, get_comments
)

# Create task
task = await create_task(session, TaskCreate(
    title="My Task",
    parent_id="proj-123.1",
    project_id="proj-123",
    task_type=TaskType.TASK,
    description="Task description",
    acceptance_criteria="- Criterion 1\n- Criterion 2"
))

# Get task
task = await get_task(session, "proj-123.1.1")

# Get children (direct or recursive)
children = await get_children(session, "proj-123.1", recursive=True)

# Get ancestors (parent → grandparent → project)
ancestors = await get_ancestors(session, "proj-123.1.1")
```

### Progress Service

```python
from ltt.services.progress_service import (
    get_or_create_progress, update_status,
    start_task, close_task, reopen_task
)

# Get/create progress record (lazy initialization)
progress = await get_or_create_progress(session, "proj-123.1", "learner-456")

# Update status
progress = await update_status(session, "proj-123.1", "learner-456", TaskStatus.IN_PROGRESS)

# Close task (validates children, validation requirements)
progress = await close_task(session, "proj-123.1", "learner-456")

# Reopen task
progress = await reopen_task(session, "proj-123.1", "learner-456")
```

### Dependency Service

```python
from ltt.services.dependency_service import (
    add_dependency, get_ready_work, get_blocking_tasks,
    is_task_blocked, detect_cycles
)

# Add dependency (task_id depends on depends_on_id)
dep = await add_dependency(session, task_id, depends_on_id, DependencyType.BLOCKS)

# Get ready work for learner (unblocked tasks)
ready = await get_ready_work(session, project_id, learner_id, task_type="task", limit=10)

# Check if task is blocked
is_blocked, blockers = await is_task_blocked(session, task_id, learner_id)

# Get blocking tasks
blockers = await get_blocking_tasks(session, task_id, learner_id)

# Detect cycles (returns list of cycles)
cycles = await detect_cycles(session, project_id)
```

### Submission & Validation Service

```python
from ltt.services.submission_service import create_submission, get_submissions
from ltt.services.validation_service import validate_submission, can_close_task

# Create submission
submission = await create_submission(
    session, task_id, learner_id,
    content="my code",
    submission_type=SubmissionType.CODE
)

# Validate submission (automatic)
validation = await validate_submission(session, submission.id)

# Check if task can be closed
can_close, message = await can_close_task(session, task_id, learner_id)
```

### Learning Services

```python
from ltt.services.learning import (
    attach_objective, get_objectives,
    get_progress, get_bloom_distribution,
    summarize_completed,
    create_content, attach_content_to_task
)

# Attach learning objective
obj = await attach_objective(
    session, task_id,
    description="Implement REST APIs",
    level=BloomLevel.APPLY
)

# Get progress for learner in project
progress = await get_progress(session, learner_id, project_id)
# Returns: total_tasks, completed_tasks, in_progress, blocked, objectives_achieved, etc.

# Get Bloom level distribution
distribution = await get_bloom_distribution(session, learner_id, project_id)
# Returns: {BloomLevel.APPLY: {"total": 5, "achieved": 3}, ...}

# Generate summary for completed task
summary = await summarize_completed(session, task_id, learner_id)

# Create and attach content
content = await create_content(session, ContentType.MARKDOWN, "# Tutorial...")
await attach_content_to_task(session, content.id, task_id)
```

### Ingestion & Export

```python
from ltt.services.ingest import ingest_project_file
from ltt.services.export import export_project

# Ingest from JSON file
result = await ingest_project_file(session, Path("project.json"), dry_run=False)
# Returns: IngestResult(project_id, task_count, objective_count, errors)

# Export to JSON
json_str = await export_project(session, project_id, format="json")

# Export to JSONL (one JSON per line)
jsonl_str = await export_project(session, project_id, format="jsonl")
```

---

## Database Connection

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

# Get database URL
db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev")

# Create engine
engine = create_async_engine(db_url, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Use session
async with async_session() as session:
    task = await get_task(session, "proj-123.1")
```

**Or use the helper**:
```python
from ltt.cli.main import get_async_session

async with get_async_session() as session:
    # Your code here
    pass
```

---

## Important Patterns

### ADR-001 Compliance

All status queries MUST join with `learner_task_progress`:

```python
# ❌ WRONG - queries task.status (doesn't exist)
task = await get_task(session, task_id)
if task.status == "closed":  # ERROR: Task has no status field

# ✅ CORRECT - queries learner_task_progress
progress = await get_or_create_progress(session, task_id, learner_id)
if progress.status == "closed":  # Correct: per-learner status
```

**Why**: Tasks are templates (shared). Status is per-learner (instance layer).

### Lazy Initialization

Progress records are created on first access:

```python
# First time accessing task for learner
progress = await get_or_create_progress(session, task_id, learner_id)
# Creates record with status='open' if doesn't exist

# SQL queries use COALESCE for same behavior
COALESCE(ltp.status, 'open')  # No record = open status
```

### PostgreSQL ARRAY Mutation

PostgreSQL ARRAYs require new list for SQLAlchemy change detection:

```python
# ❌ WRONG - mutation not detected
task.content_refs.append(content_id)
await session.commit()  # No update

# ✅ CORRECT - create new list
content_refs = list(task.content_refs) if task.content_refs else []
content_refs.append(content_id)
task.content_refs = content_refs  # Assign new list
await session.commit()  # Update detected
```

### Hierarchical ID Generation

```python
from ltt.utils.ids import generate_task_id, generate_entity_id

# Task IDs (hierarchical)
project_id = generate_task_id(None, "proj", lambda _: 0)  # proj-a1b2
child_id = generate_task_id("proj-a1b2", "proj", lambda _: 1)  # proj-a1b2.1

# Entity IDs (non-hierarchical)
learner_id = generate_entity_id("learner")  # learner-abc123def
content_id = generate_entity_id("cnt")      # cnt-xyz789
```

---

## JSON Schema Reference

### Project Structure

```json
{
  "title": "Project Title",
  "description": "What you're building and why",
  "narrative_context": "Real-world motivation (optional)",
  "learning_objectives": [
    {"level": "create", "description": "Build a full-stack app"}
  ],
  "content": "## Architecture\n\n...",
  "epics": [
    {
      "title": "Epic Title",
      "description": "Feature area description",
      "learning_objectives": [...],
      "content": "...",
      "tutor_guidance": {
        "teaching_approach": "Start with examples",
        "discussion_prompts": ["Why is this important?"],
        "common_mistakes": ["Off-by-one errors"],
        "hints_to_give": ["Check the bounds", "Use a debugger"]
      },
      "tasks": [
        {
          "title": "Task Title",
          "description": "Specific component to build",
          "acceptance_criteria": "- Criterion 1\n- Criterion 2",
          "learning_objectives": [...],
          "priority": 0,
          "content": "...",
          "tutor_guidance": {...},
          "dependencies": ["Other Task Title"],
          "subtasks": [
            {
              "title": "Subtask Title",
              "description": "Atomic piece of work",
              "acceptance_criteria": "...",
              "learning_objectives": [...],
              "content": "...",
              "tutor_guidance": {...},
              "priority": 0
            }
          ]
        }
      ]
    }
  ]
}
```

**See [docs/schema/project-ingestion.md](docs/schema/project-ingestion.md) for complete field-by-field guide.**

---

## Common Tasks

### Creating a Project from JSON

```bash
# 1. Create or generate project.json
#    (Use LLM with docs/schema/project-ingestion.md for conversion)

# 2. Validate structure
python -m ltt.cli.main ingest project project.json --dry-run

# 3. Import
python -m ltt.cli.main ingest project project.json
```

### Checking Learner Progress

```python
from ltt.services.learning import get_progress

progress = await get_progress(session, learner_id, project_id)

print(f"Completed: {progress.completed_tasks}/{progress.total_tasks}")
print(f"Percentage: {progress.completion_percentage}%")
print(f"Objectives: {progress.objectives_achieved}/{progress.total_objectives}")
```

### Finding Ready Work

```python
from ltt.services.dependency_service import get_ready_work

# Get tasks learner can work on (unblocked, not closed)
ready = await get_ready_work(
    session,
    project_id="proj-123",
    learner_id="learner-456",
    task_type="task",  # Optional filter
    limit=10
)

# Returns list of Task objects, ordered by:
# 1. Status (in_progress first, then open)
# 2. Priority (P0 first)
# 3. Hierarchy depth (parents before children)
# 4. Age (oldest first)
```

### Submitting Work

```python
from ltt.services.submission_service import create_submission
from ltt.services.validation_service import validate_submission

# Create submission
submission = await create_submission(
    session,
    task_id="proj-123.1.1",
    learner_id="learner-456",
    content="SELECT * FROM surveys WHERE queue_time > 500",
    submission_type=SubmissionType.SQL
)

# Validate (automatic)
validation = await validate_submission(session, submission.id)

if validation.passed:
    # Can close task (if it's a subtask)
    await close_task(session, task_id, learner_id)
else:
    print(f"Failed: {validation.error_message}")
```

---

## Prerequisites

- **Python**: 3.12+
- **Node.js**: 24 (`nvm use 24` — v24.12.0 confirmed. Node 18 is in PATH by default on this machine; always run `nvm use 24` before frontend work or the dev server will refuse to start)
- **Docker**: For PostgreSQL and MySQL
- **uv**: Python package manager

---

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev

# LTI (required for LTI to work — if unset, LTI endpoints are disabled)
LTT_REDIS_URL=redis://localhost:6379/0
LTT_FRONTEND_URL=http://localhost:3000          # Where /lti/launch redirects to
LTI_PLATFORM_URL=https://imbizo.alx-ai-tools.com  # CSP frame-ancestors

# Optional LTI overrides
LTI_PLATFORM_CONFIG=configs/lti/platform.json   # Platform registration
LTI_PRIVATE_KEY=configs/lti/private.key          # RSA private key
LTI_PUBLIC_KEY=configs/lti/public.key            # RSA public key

# Debug (enables /lti/debug/* and debug button in frontend)
DEBUG=true
NEXT_PUBLIC_DEBUG=true

# Required for Alembic migrations
PYTHONPATH=services/ltt-core/src
```

**Default database** (docker-compose):
- Host: localhost:5432
- Database: ltt_dev
- User: ltt_user
- Password: ltt_password

**Redis** (docker-compose):
- Host: localhost:6379
- Database: 0

---

## Testing Fixtures

### Backend (pytest)

Available in tests via `conftest.py`:

```python
@pytest.mark.asyncio
async def test_my_feature(async_session):
    """Test with async database session."""
    # async_session is a fresh database session for this test
    task = await create_task(async_session, TaskCreate(...))
    assert task.id is not None
```

**ltt-core fixtures** (`services/ltt-core/tests/conftest.py`):
- `async_session` - Fresh async database session (rolled back after test)
- `tmp_path` - Temporary directory (pytest built-in)

**api-server fixtures** (`services/api-server/tests/conftest.py`):
- `test_settings` / `test_settings_auth` - Settings with auth_enabled=False/True
- `async_engine` / `async_session` / `session_factory` - Test DB (create_all/drop_all per test)
- `fake_redis_client` / `lti_storage` - fakeredis-backed Redis + LTI storage
- `app` / `client` - FastAPI test app + httpx AsyncClient (auth_enabled=False)
- `app_auth` / `client_auth` - Same with auth_enabled=True
- `seed_launch` - Factory to populate launch sessions in fake Redis

### Frontend (Vitest)

Test infrastructure in `apps/web/`:
- `vitest.config.ts` - Vitest config (jsdom, `@/` path alias, setup file)
- `src/test/setup.ts` - jest-dom matchers + jsdom polyfills (scrollIntoView)
- `src/test/helpers.tsx` - `renderWithProviders()` wrapper (QueryClientProvider)

Tests co-located with source: `src/**/*.test.{ts,tsx}`

---

## Key Files to Know

### Configuration
- `pyproject.toml` - Workspace root, dependencies, pytest config, ruff settings
- `apps/web/package.json` - Frontend dependencies, scripts (dev, build, test)
- `apps/web/vitest.config.ts` - Frontend test config (jsdom, path aliases)
- `infrastructure/docker/docker-compose.yml` - PostgreSQL 17 + MySQL 8.0 + Redis 7 setup
- `configs/lti/platform.json` - LTI platform registration (issuer, client_id, endpoints)
- `configs/lti/private.key` / `public.key` - RSA keys for JWT (private key gitignored)
- `.env` - Environment variables (create from `.env.example`)

### Models
- `services/ltt-core/src/ltt/models/__init__.py` - All models exported
- `services/ltt-core/src/ltt/models/task.py` - Task, TaskCreate, TaskUpdate, TaskModel
- `services/ltt-core/src/ltt/models/progress.py` - LearnerTaskProgress
- `services/ltt-core/src/ltt/models/submission.py` - Submission, Validation
- `services/ltt-core/src/ltt/models/lti_mapping.py` - LTIUserMapping (lti_sub/iss → learner_id)
- `services/ltt-core/src/ltt/models/lti_launch.py` - LTILaunch (persisted launch data)

### LTI Integration
- `services/api-server/src/api/lti/routes.py` - `/lti/login`, `/lti/launch`, `/lti/jwks` endpoints
- `services/api-server/src/api/lti/adapter.py` - PyLTI1p3 FastAPI adapter classes
- `services/api-server/src/api/lti/users.py` - `get_or_create_lti_learner()` user mapping
- `services/api-server/src/api/lti/grades.py` - AGS grade passback to Open edX
- `services/api-server/src/api/lti/storage.py` - Redis-backed launch data storage
- `apps/web/src/lib/lti.ts` - Frontend LTI context (parse, store, iframe detection)

### Services
- `services/ltt-core/src/ltt/services/task_service.py` - Most commonly used
- `services/ltt-core/src/ltt/services/dependency_service.py` - Ready work, blocking
- `services/ltt-core/src/ltt/services/learning/objectives.py` - Learning objectives

### Documentation
- `docs/lti/` - **Critical** - Full LTI spec, architecture, cleanup plan
- `docs/lti/cleanup/` - Code to remove for production (standalone mode artifacts)
- `docs/schema/project-ingestion.md` - Complete schema guide
- `docs/cli/usage.md` - Full CLI reference
- `docs/adr/` - Architecture Decision Records (ADR-001, ADR-002, ADR-003)

---

## Quick Reference

### Status Transitions

```
open → in_progress  ✅ Always allowed
open → blocked      ✅ When dependency incomplete

in_progress → open      ✅ Allowed
in_progress → blocked   ✅ When dependency incomplete
in_progress → closed    ✅ If validation passes (for subtasks)

blocked → open          ✅ Allowed
blocked → in_progress   ✅ When dependencies complete

closed → open           ✅ Only via go_back (requires reason)
```

### Task Types

- `project` - Root container
- `epic` - Major feature area
- `task` - Cohesive work unit (can have subtasks)
- `subtask` - Atomic work item (requires validation to close)

### Priority Levels

- `0` - Critical (foundational, blocks everything)
- `1` - High
- `2` - Medium (default)
- `3` - Low
- `4` - Nice-to-have

---

## Troubleshooting

### "Task has no status"
**Cause**: Trying to access `task.status` (doesn't exist in template layer)
**Fix**: Use `learner_task_progress` table via `get_or_create_progress()`

### "Validation failed: cannot close task"
**Cause**: Subtask requires passing validation
**Fix**: Submit work that passes acceptance criteria

### "Task is blocked"
**Cause**: Dependencies not complete
**Fix**: Check `get_blocking_tasks()`, complete dependencies first

### "Foreign key violation: learner not found"
**Cause**: Using non-existent learner_id
**Fix**: Create learner first with `LearnerModel` or CLI

### Tests failing after model changes
**Cause**: Migration not run
**Fix**: `PYTHONPATH=services/ltt-core/src uv run alembic upgrade head`

---

## Performance Notes

### Recursive CTEs Used For:
- Ready work calculation (transitive blocking)
- Cycle detection (graph traversal)
- Hierarchical queries

### Indexes Created For:
- `tasks.parent_id`, `tasks.project_id`
- `learner_task_progress(task_id, learner_id)`
- `dependencies.task_id`, `dependencies.depends_on_id`
- `submissions(task_id, learner_id)`

### Query Patterns

**Always use COALESCE for learner status**:
```sql
COALESCE(ltp.status, 'open')
-- No progress record = open status (lazy initialization)
```

**Always join learner_task_progress for status**:
```sql
FROM tasks t
LEFT JOIN learner_task_progress ltp
  ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
```

---

## Test Coverage

### Backend (Python — pytest)

- **ltt-core**: 153 tests (models, services, tools, CLI, ingestion/export)
- **api-server**: 75 tests (LTI auth, dev login, OIDC launch, JWKS, protected endpoints, workspace context)
- **agent-tutor**: 50 tests

### Frontend (TypeScript — Vitest + React Testing Library)

- **Type converters**: 8 tests — `queryResultToExecutionResult`, `pythonResultToExecutionResult`
- **API layer**: 12 tests — `lttFetch` headers, `streamChat` payload shape + SSE parsing
- **ChatPanel**: 10 tests — workspace context assembly (SQL/Python), form behavior, streaming
- **LTI context**: 14 tests — parse/store/get, `devLogin`/`devLogout`
- **Utilities**: 21 tests — `parseTaskReferences`, `formatDuration`, status helpers
- **Workspace store**: 18 tests — Zustand state, setters, drawer, legacy alias

### Run Specific Test Suites

```bash
# Backend: ltt-core
uv run pytest services/ltt-core/tests/test_basic.py -v
uv run pytest services/ltt-core/tests/services/test_task_service.py -v
uv run pytest services/ltt-core/tests/services/test_dependency_service.py -v
uv run pytest services/ltt-core/tests/services/test_learning_*.py -v
uv run pytest services/ltt-core/tests/tools/ -v
uv run pytest services/ltt-core/tests/services/test_ingest.py services/ltt-core/tests/services/test_export.py -v

# Backend: api-server (LTI + auth + workspace context)
uv run --package api-server pytest services/api-server/tests/ -v

# Frontend (must run from apps/web/ — not the repo root)
cd apps/web && npm test
```

---

## Implementation Status

**All Core Phases Complete** ✅

| Area | Status | Tests |
|------|--------|-------|
| **Backend: ltt-core** | | |
| Data Layer | ✅ | 3 |
| Task Management | ✅ | 36 |
| Dependencies | ✅ | 23 |
| Submissions & Validation | ✅ | 22 |
| Learning & Progress | ✅ | 34 |
| Agent Tools | ✅ | 26 |
| Admin CLI & Ingestion | ✅ | 23 |
| **Backend: api-server** | | |
| LTI Storage | ✅ | 8 |
| LTI User Mapping | ✅ | 8 |
| Auth Middleware | ✅ | 7 |
| Dev Login/Logout | ✅ | 9 |
| OIDC Launch Flow | ✅ | 9 |
| JWKS Endpoint | ✅ | 3 |
| Debug Endpoints | ✅ | 6 |
| Protected Endpoints | ✅ | 8 |
| Workspace Context (LLM) | ✅ | 17 |
| **Frontend** | | |
| Type Converters | ✅ | 8 |
| API Layer (streamChat) | ✅ | 12 |
| ChatPanel Integration | ✅ | 10 |
| LTI Context | ✅ | 14 |
| Utilities | ✅ | 21 |
| Workspace Store | ✅ | 18 |
| **Total** | | **~325** |

See [BUILD-STATUS.md](BUILD-STATUS.md) for detailed phase reports.

---

## Future Development

### Ready for Implementation
- MCP server integration (expose agent tools)
- Custom validation rules (code execution, SQL checks)
- Project versioning

### Technical Debt
- Fix 162 datetime.utcnow() deprecation warnings
- Add CLI command tests (services tested, not Typer commands)
- JSON Schema validation for ingestion

---

## Links

- **Schema Guide**: [docs/schema/project-ingestion.md](docs/schema/project-ingestion.md)
- **CLI Reference**: [docs/cli/usage.md](docs/cli/usage.md)
- **Build Status**: [BUILD-STATUS.md](BUILD-STATUS.md)
- **Architecture Decisions**: [docs/architecture/adr/](docs/architecture/adr/)
- **Beads (Original)**: https://github.com/steveyegge/beads
