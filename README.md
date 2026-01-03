# Learning Task Tracker (LTT)

> A Python-based learning task management system adapted from [beads](https://github.com/steveyegge/beads), designed to power AI tutoring agents at scale.

[![Tests](https://img.shields.io/badge/tests-190%20passing-brightgreen)]() [![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen)]() [![Python](https://img.shields.io/badge/python-3.12%2B-blue)]() [![PostgreSQL](https://img.shields.io/badge/postgresql-17-blue)]()

---

## What is LTT?

LTT provides a **data tooling layer** that enables AI tutoring agents to:
- 📚 Guide learners through structured, hierarchical projects
- 📊 Track progress per learner using a two-layer architecture
- ✅ Validate submissions as proof of work
- 🎯 Provide pedagogically-aware context at every level
- 🤖 Support stateless LLM agents with rich runtime tools

**Key Insight**: At any point in a learning journey, an LLM tutor should have enough **broad context** (what we're building) and **specific guidance** (what to do now) to effectively teach.

---

## Architecture

### Two-Layer Architecture (ADR-001)

```
┌─────────────────────────────────────────────────────┐
│  Template Layer (Shared Curriculum)                 │
│  • tasks (project/epic/task/subtask)                │
│  • learning_objectives (Bloom's taxonomy)           │
│  • dependencies (blocking relationships)            │
│  • content (tutorials, examples)                    │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  Instance Layer (Per-Learner)                       │
│  • learner_task_progress (status, timestamps)       │
│  • submissions (proof of work)                      │
│  • validations (pass/fail checks)                   │
│  • status_summaries (progress notes)                │
└─────────────────────────────────────────────────────┘
```

This separation allows:
- **One curriculum** used by thousands of learners
- **Independent progress** tracking per learner
- **Pedagogical enrichment** (objectives, guidance) separated from execution (status, submissions)

See [ADR-001](python-port/docs/adr/001-learner-scoped-task-progress.md) for detailed rationale.

---

## Features

### ✅ Implemented (Phases 1-5, 7-8)

#### Data Layer (Phase 1)
- 14 Pydantic models with validation
- 14 SQLAlchemy async models
- PostgreSQL 17 database
- Alembic migrations
- Hierarchical ID generation

#### Task Management (Phase 2)
- CRUD for tasks at all levels (project → epic → task → subtask)
- Status transitions with validation (open → in_progress → closed)
- Hierarchy traversal (ancestors, children)
- Comments (shared and private)
- Status state machine

#### Dependencies (Phase 3)
- Blocking relationships (BLOCKS, PARENT_CHILD, RELATED)
- Cycle detection (prevents circular dependencies)
- Ready work calculation (what should I do next?)
- Learner-scoped blocking (per ADR-001)
- Transitive blocking with recursive CTEs

#### Submissions & Validation (Phase 4)
- Submission types: code, SQL, text, Jupyter cells, result sets
- Automatic validation on submission
- Attempt tracking
- Validation gates for task closure
- SimpleValidator (MVP: non-empty check)

#### Learning & Progress (Phase 5)
- Learning objectives (Bloom's taxonomy)
- Progress tracking per learner
- Hierarchical summarization
- Content management
- Bloom level distribution
- Objective achievement (derived from validations)

#### Agent Tools (Phase 7)
- **Navigation**: `get_ready`, `show_task`, `get_context`
- **Progress**: `start_task`, `submit` (auto-closes on validation pass)
- **Feedback**: `add_comment`, `get_comments`
- **Control**: `go_back`, `request_help`
- Tool registry for MCP/function calling
- Stateless design (LangGraph manages sessions)
- Submission-driven task completion (ADR-002)

#### Admin CLI & Ingestion (Phase 8)
- **Project management**: create, list, show, export
- **Ingestion**: Import projects from JSON
- **Task management**: create, add objectives
- **Content management**: create, attach
- **Learner management**: create, list, progress
- **Export**: JSON/JSONL formats with roundtrip support
- **Pedagogical fields**: `tutor_guidance`, `narrative_context`

### 🔜 Future Enhancements

- FastAPI REST endpoints
- MCP server integration
- LLM-powered project conversion
- Real-time validation with custom rules
- Analytics dashboard
- Project versioning

---

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 17
- uv package manager

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/beadslocal.git
cd beadslocal

# Install dependencies
uv sync

# Start PostgreSQL
docker-compose up -d

# Run migrations
PYTHONPATH=src uv run alembic upgrade head
```

### Verify Installation

```bash
# Run all tests (should see 167 passing)
uv run pytest tests/ -v

# Check code quality
uv run ruff check src/
```

---

## Usage

### Admin CLI

```bash
# Create a project manually
python -m ltt.cli.main project create "My Learning Project"

# Import a structured project from JSON
python -m ltt.cli.main ingest project path/to/project.json --dry-run
python -m ltt.cli.main ingest project path/to/project.json

# Export for backup
python -m ltt.cli.main project export proj-abc123 --output backup.json

# Create learner and track progress
python -m ltt.cli.main learner create
python -m ltt.cli.main learner progress learner-123 proj-abc123
```

See [CLI-USAGE-GUIDE.md](docs/CLI-USAGE-GUIDE.md) for complete command reference.

### Agent Tools (Python API)

```python
from ltt.tools import execute_tool, get_tool_schemas

# Get available tools for LLM agents
schemas = get_tool_schemas()  # OpenAI-compatible

# Execute a tool
async with get_async_session() as session:
    result = await execute_tool(
        "get_ready",
        {"project_id": "proj-abc123"},
        learner_id="learner-456",
        session=session
    )

    # result.tasks → List of ready tasks (in_progress first)
```

### Creating Projects with LLMs

LTT includes comprehensive schema documentation designed for LLM-based project creation:

**Workflow**:
1. Have unstructured learning content (tutorials, course outlines)
2. Use an LLM with [SCHEMA-FOR-LLM-INGESTION.md](docs/SCHEMA-FOR-LLM-INGESTION.md)
3. LLM converts to structured JSON with:
   - Hierarchical breakdown (project → epic → task → subtask)
   - Learning objectives (Bloom's taxonomy)
   - Acceptance criteria (validation rules)
   - Tutor guidance (teaching strategies, hints, common mistakes)
   - Narrative context (real-world motivation)
4. Import with `ltt ingest project generated.json`

See [SCHEMA-FOR-LLM-INGESTION.md](docs/SCHEMA-FOR-LLM-INGESTION.md) for complete guide.

---

## Project Structure

```
beadslocal/
├── src/ltt/
│   ├── models/              # Pydantic + SQLAlchemy models
│   │   ├── task.py          # Core task model (template layer)
│   │   ├── progress.py      # Learner progress (instance layer)
│   │   ├── submission.py    # Submissions & validations
│   │   ├── dependency.py    # Task relationships
│   │   ├── objective.py     # Learning objectives
│   │   └── ...
│   │
│   ├── services/            # Business logic layer
│   │   ├── task_service.py      # Task CRUD, hierarchy
│   │   ├── progress_service.py  # Status transitions
│   │   ├── dependency_service.py # Dependencies, ready work
│   │   ├── submission_service.py # Submissions
│   │   ├── validation_service.py # Validation logic
│   │   ├── learning/            # Learning services
│   │   │   ├── objectives.py    # Learning objectives
│   │   │   ├── progress.py      # Progress tracking
│   │   │   ├── summarization.py # Hierarchical summaries
│   │   │   └── content.py       # Content management
│   │   ├── ingest.py            # JSON ingestion
│   │   └── export.py            # Project export
│   │
│   ├── tools/               # Agent runtime interface
│   │   ├── navigation.py    # get_ready, show_task, get_context
│   │   ├── progress.py      # start_task, submit
│   │   ├── feedback.py      # add_comment, get_comments
│   │   ├── control.py       # go_back, request_help
│   │   └── schemas.py       # Pydantic I/O models
│   │
│   ├── cli/                 # Admin CLI
│   │   └── main.py          # Typer commands
│   │
│   ├── db/                  # Database
│   │   ├── session.py       # Async session management
│   │   └── migrations/      # Alembic migrations
│   │
│   └── utils/               # Utilities
│       └── ids.py           # Hierarchical ID generation
│
├── tests/                   # Test suite (167 tests)
│   ├── services/            # Service layer tests
│   ├── tools/               # Agent tools tests
│   └── conftest.py          # Pytest fixtures
│
├── docs/                    # Documentation
│   ├── SCHEMA-FOR-LLM-INGESTION.md  # LLM project conversion guide
│   ├── CLI-USAGE-GUIDE.md           # Admin CLI reference
│   └── BUILD-STATUS.md              # Implementation status
│
└── python-port/docs/        # Technical specifications
    ├── PRD.md               # Product requirements
    ├── 01-data-models.md    # Model specs
    ├── 02-task-management.md
    ├── 03-dependencies.md
    ├── 04-submissions-validation.md
    ├── 05-learning-progress.md
    ├── 07-agent-tools.md
    ├── 08-admin-cli.md
    └── adr/                 # Architecture decisions
```

---

## Key Concepts

### Hierarchical Tasks

```
Project: "Build E-commerce Site"
  │
  ├── Epic: "Backend API"
  │   ├── Task: "User Authentication"
  │   │   ├── Subtask: "Create JWT token function"
  │   │   ├── Subtask: "Build login endpoint"
  │   │   └── Subtask: "Add password hashing"
  │   └── Task: "Product Catalog"
  │
  └── Epic: "Frontend UI"
      └── Task: "Shopping Cart"
```

- **Unlimited nesting** via `parent_id`
- **Hierarchical IDs**: `proj-a1b2.1.2.1`
- **Context at every level**: broad (project) → specific (subtask)

### Learner-Scoped Progress

**Template Layer** (shared):
- Task definition: title, description, acceptance criteria
- Learning objectives, content, dependencies

**Instance Layer** (per-learner):
- Status: open → in_progress → blocked → closed
- Submissions and validations
- Progress timestamps
- Status summaries

**Result**: 1,000 learners can work on same project independently.

### Learning Objectives (Bloom's Taxonomy)

```python
{
  "level": "apply",
  "description": "Implement JWT authentication in FastAPI"
}
```

**Levels**: remember → understand → apply → analyze → evaluate → create

**Achievement**: Derived from passing validations, not stored separately.

### Pedagogical Guidance

**`tutor_guidance`** (Task/Subtask level):
```json
{
  "teaching_approach": "Start with real-world context before SQL",
  "discussion_prompts": ["What does 500 minutes mean in real life?"],
  "common_mistakes": ["Using = instead of LIKE"],
  "hints_to_give": ["Try SHOW TABLES first", "Check column names"]
}
```

**`narrative_context`** (Project level):
```
"This data comes from President Naledi's water quality initiative. You are
helping analyze survey data that will impact real communities..."
```

These fields guide **HOW** LLM tutors teach, not just **WHAT** they teach.

---

## Documentation

### User Documentation
- **[CLI-USAGE-GUIDE.md](docs/CLI-USAGE-GUIDE.md)** - Complete CLI command reference with examples
- **[SCHEMA-FOR-LLM-INGESTION.md](docs/SCHEMA-FOR-LLM-INGESTION.md)** - Comprehensive guide for structuring projects (designed for LLMs)

### Technical Documentation
- **[PRD.md](python-port/docs/PRD.md)** - Product requirements and system architecture
- **[BUILD-STATUS.md](BUILD-STATUS.md)** - Implementation status, test counts, phase completion
- **Module Specs**: [02-task-management.md](python-port/docs/02-task-management.md), [03-dependencies.md](python-port/docs/03-dependencies.md), [04-submissions-validation.md](python-port/docs/04-submissions-validation.md), etc.

### Architecture Decision Records
- **[ADR-001](python-port/docs/adr/001-learner-scoped-task-progress.md)** - Two-layer architecture (template + instance)
- **[ADR-002](python-port/docs/adr/002-submission-driven-task-completion.md)** - Submission-driven task completion (auto-close on validation)

### Implementation Notes
- **Phase Completion Reports**: [src/ltt/tempdocs/](src/ltt/tempdocs/) - Detailed reports for each phase

---

## Implementation Status

**All Core Phases Complete** ✅

| Phase | Module | Tests | Status |
|-------|--------|-------|--------|
| **1** | Data Layer | 3 | ✅ Complete |
| **2** | Task Management | 36 | ✅ Complete |
| **3** | Dependencies | 23 | ✅ Complete |
| **4** | Submissions & Validation | 22 | ✅ Complete |
| **5** | Learning & Progress | 34 | ✅ Complete |
| **7** | Agent Tools | 26 | ✅ Complete |
| **8** | Admin CLI & Ingestion | 23 | ✅ Complete |
| **E2E** | End-to-End Integration | 15 | ✅ Complete |
| | **Total** | **190** | **All Passing** ✅ |

**Coverage**: 98% overall (services), 100% models

See [BUILD-STATUS.md](BUILD-STATUS.md) for detailed implementation status.

---

## Quick Start

### 1. Setup

```bash
# Install dependencies
uv sync

# Start PostgreSQL 17
docker-compose up -d

# Run migrations
PYTHONPATH=src uv run alembic upgrade head
```

### 2. Create Your First Project

**Option A: Manual Creation**
```bash
python -m ltt.cli.main project create "Build Todo API" \
  --description "Learn FastAPI by building a REST API"

python -m ltt.cli.main task create "Set up FastAPI" \
  --parent proj-abc123 \
  --type task
```

**Option B: Import from JSON** (Recommended)
```bash
# Create project.json (see docs/SCHEMA-FOR-LLM-INGESTION.md)
# Or use an LLM to convert your tutorial/course outline

# Validate
python -m ltt.cli.main ingest project project.json --dry-run

# Import
python -m ltt.cli.main ingest project project.json
```

### 3. Create Learners and Track Progress

```bash
# Create learner
python -m ltt.cli.main learner create

# Check progress
python -m ltt.cli.main learner progress learner-abc123 proj-xyz789
```

### 4. Use Agent Tools (Python)

```python
from ltt.tools import get_ready, start_task, submit

# Get ready work for learner
result = await get_ready(
    GetReadyInput(project_id="proj-123"),
    learner_id="learner-456",
    session
)

# Start a task
result = await start_task(
    StartTaskInput(task_id="proj-123.1.1"),
    learner_id="learner-456",
    session
)

# Submit work (auto-closes on validation pass)
result = await submit(
    SubmitInput(
        task_id="proj-123.1.1",
        content="def hello(): return 'world'",
        submission_type="code"
    ),
    learner_id="learner-456",
    session
)
# result.status == "closed" if validation passed
# result.message == "Validation successful, task complete"
```

---

## Development

### Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Specific module
uv run pytest tests/services/test_task_service.py -v

# With coverage
uv run pytest tests/ --cov=src/ltt --cov-report=term-missing

# Fast (quiet mode)
uv run pytest tests/ -q
```

### Code Quality

```bash
# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Type checking
uv run mypy src/
```

### Database Management

```bash
# Create new migration
PYTHONPATH=src uv run alembic revision --autogenerate -m "Description"

# Run migrations
PYTHONPATH=src uv run alembic upgrade head

# Rollback
PYTHONPATH=src uv run alembic downgrade -1

# View history
PYTHONPATH=src uv run alembic history
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Language** | Python 3.12+ | Modern Python with type hints |
| **Type Safety** | Pydantic v2 | Validation, serialization |
| **Database** | PostgreSQL 17 | JSONB, ARRAY, recursive CTEs |
| **ORM** | SQLAlchemy 2.0 | Async support, type hints |
| **Migrations** | Alembic | Schema versioning |
| **CLI** | Typer | Auto-docs, Pydantic integration |
| **Testing** | pytest + pytest-asyncio | Async test support |
| **Linting** | Ruff | Fast Python linter |

---

## Core Features

### Status State Machine

```
     ┌──────────┐
     │ blocked  │←────┐
     └────┬─────┘     │
          │           │
          ▼           │
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │   open   │─→│in_progress│─→│ closed   │
  └──────────┘  └──────────┘  └────┬─────┘
       ▲                           │
       └───────────────────────────┘
              go_back (reopen)
```

### Dependency Types

- **`BLOCKS`**: Task B waits for Task A to close
- **`PARENT_CHILD`**: Parent can't close until children close
- **`RELATED`**: Informational link, no blocking

### Validation Flow (ADR-002)

```
submit()
   │
   ├── Create Submission
   │
   ├── Validate (automated)
   │
   └── If PASS ──────────────────┐
       │                         │
       ▼                         ▼
   close_task()            If FAIL
   (auto-close)                  │
       │                         ▼
       ▼                    Return error
   status: "closed"         message
   message: "task complete"
```

**Key behavior**: Tasks auto-close when validation passes. No separate close step needed.
See [ADR-002](python-port/docs/adr/002-submission-driven-task-completion.md) for details.

---

## Examples

### Example 1: Simple Project Structure

```json
{
  "title": "Learn SQL Basics",
  "narrative_context": "Help analyze real water quality data from rural communities.",
  "epics": [
    {
      "title": "Fundamentals",
      "tasks": [
        {
          "title": "SELECT Queries",
          "subtasks": [
            {"title": "Select all columns"},
            {"title": "Select specific columns"},
            {"title": "Use WHERE clause"}
          ]
        }
      ]
    }
  ]
}
```

### Example 2: Subtask with Tutor Guidance

```json
{
  "title": "Filter long queue times",
  "description": "Write WHERE clause to find surveys where wait time > 500 minutes",
  "acceptance_criteria": "- Query returns only queue_time > 500\n- Uses correct column name",
  "tutor_guidance": {
    "teaching_approach": "Start with human impact before SQL",
    "discussion_prompts": [
      "500 minutes is over 8 hours. What does waiting that long mean?"
    ],
    "common_mistakes": [
      "Using = instead of >",
      "Putting numbers in quotes"
    ],
    "hints_to_give": [
      "Which operator means 'greater than'?",
      "Numbers don't need quotes in SQL"
    ]
  }
}
```

---

## Database Schema Highlights

### Template Layer
- `tasks` - Work item definitions (shared)
- `learning_objectives` - Bloom's taxonomy objectives
- `dependencies` - Blocking relationships
- `content` - Learning materials
- `acceptance_criteria` - Validation rules

### Instance Layer
- `learner_task_progress` - Per-learner status
- `submissions` - Proof of work
- `validations` - Pass/fail results
- `status_summaries` - Versioned progress notes

### Shared
- `learners` - User profiles
- `comments` - Task feedback (shared or private)
- `events` - Audit trail

See [01-data-models.md](python-port/docs/01-data-models.md) for complete schema.

---

## Testing

**190 tests across all phases, all passing**

```bash
# Run all tests
PYTHONPATH=src uv run pytest tests/ -v

# Fast run
PYTHONPATH=src uv run pytest tests/ -q

# Specific module
PYTHONPATH=src uv run pytest tests/services/test_dependency_service.py -v
PYTHONPATH=src uv run pytest tests/tools/ -v
```

### End-to-End Integration Tests

Run comprehensive integration tests that validate the full agentic workflow:

```bash
PYTHONPATH=src uv run pytest tests/test_e2e_agentic_workflow.py -v
```

**What's Tested** (15 test cases):
- ✅ **Database connectivity** - Verifies PostgreSQL is running
- ✅ **Project ingestion** - Imports from `project_data/DA/MN_Part1/structured/water_analysis_project.json`
- ✅ **Initial state** - Ready work shows only unblocked tasks
- ✅ **Task lifecycle** - start_task, submit, validation, auto-close
- ✅ **Hierarchical closure** - Parent closes only after children
- ✅ **Epic blocking propagation** - Epic dependencies block child tasks
- ✅ **Multi-learner isolation**:
  - Status changes (Learner A's progress doesn't affect Learner B)
  - Comments (private comments are learner-scoped)
  - Progress tracking (independent completion counts)
  - Blocking (dependencies resolved per-learner)
- ✅ **Go back** - Reopening closed tasks
- ✅ **Submission attempts** - Attempt numbers increment correctly
- ✅ **Error handling** - Invalid submission types, blocked tasks

**Test Coverage**:
- Data models: 99%
- Services: 95%
- Utils: 100%
- Overall: 98%

---

## Contributing

### Code Style

- Modern Python 3.12+ (type hints, match statements)
- Async-first (all database operations async)
- Pydantic for validation
- Ruff for linting/formatting

### Testing Requirements

- All new features must have tests
- Maintain >95% coverage
- Use pytest-asyncio for async tests
- Follow existing test patterns

### Commit Convention

Follow conventional commits:
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation updates
- `test:` Test additions/changes
- `refactor:` Code refactoring

---

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://ltt:ltt@localhost:5432/ltt

# Required for Alembic
PYTHONPATH=src
```

---

## FAQ

**Q: What's the difference between Agent Tools and Admin CLI?**
- **Agent Tools**: Runtime interface for LLM agents (read operations, submissions)
- **Admin CLI**: Setup interface for instructors (create projects, manage content)

**Q: How do learning objectives work?**
- Attached to tasks at any level using Bloom's taxonomy
- Achievement is *derived* from passing validations
- Tracked via `get_progress()` and `get_bloom_distribution()`

**Q: Can dependencies cross epics?**
- Yes! Dependencies are unconstrained (any task can depend on any other task in same project)
- Common pattern: Frontend epic depends on Backend epic tasks
- Title-based resolution during ingestion

**Q: What's the difference between `content` and `tutor_guidance`?**
- **`content`**: Tutorial material for learners (code examples, explanations)
- **`tutor_guidance`**: Meta-guidance for LLM tutors (teaching strategies, common mistakes, hints)

**Q: How does validation work?**
- Currently: SimpleValidator (non-empty check)
- Future: Custom validators (code tests, SQL result checks, etc.)
- Subtasks require passing validation to close

---

## Roadmap

### ✅ Completed
- [x] Data layer with two-tier architecture
- [x] Task management with hierarchy
- [x] Dependency resolution and ready work
- [x] Submissions and validation
- [x] Learning objectives and progress tracking
- [x] Agent tools for LLM runtime
- [x] Admin CLI and JSON ingestion
- [x] Pedagogical guidance fields
- [x] Comprehensive documentation

### 🔜 Next Steps
- [ ] Integration testing (multi-learner scenarios)
- [ ] Fix datetime deprecation warnings
- [ ] FastAPI REST endpoints
- [ ] MCP server implementation
- [ ] Custom validation rules
- [ ] Project versioning
- [ ] LLM-powered project conversion

---

## License

MIT

---

## Acknowledgments

Adapted from [beads](https://github.com/steveyegge/beads) by Steve Yegge.

Core architectural patterns (hierarchical IDs, dependency resolution, ready work calculation) borrowed from beads with gratitude.
