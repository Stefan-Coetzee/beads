# LTT Admin CLI - Usage Guide

> Command-line interface for project setup, ingestion, and administration.

## Quick Start

```bash
# Initialize database
ltt db init

# Create a project manually
ltt project create "Build Todo API" --description "Learn FastAPI"

# Import a project from JSON
ltt ingest project path/to/project.json

# List all projects
ltt project list

# Create a learner
ltt learner create

# Check learner progress
ltt learner progress learner-abc123 proj-xyz789
```

---

## Installation & Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 17 (via Docker or local)
- uv package manager

### Database Setup

```bash
# Start PostgreSQL (Docker)
docker-compose up -d

# Initialize database schema
ltt db init
```

This runs all Alembic migrations and creates tables.

---

## Command Reference

### Project Management

#### `ltt project create`

Create a new empty project.

```bash
ltt project create "My Project" \
  --description "Project description"
```

**Options**:
- `--description, -d`: Project description (optional)

**Output**:
```
Created project: proj-a1b2
  Title: My Project
```

---

#### `ltt project list`

List all projects in the system.

```bash
ltt project list --limit 20
```

**Options**:
- `--limit, -n`: Maximum projects to show (default: 20)

**Output**:
```
○ proj-a1b2: Build Todo API
○ proj-c3d4: E-commerce Site
○ proj-e5f6: Data Science Portfolio
```

---

#### `ltt project show`

Show detailed information about a project.

```bash
ltt project show proj-a1b2
```

**Output**:
```
Project: proj-a1b2
  Title: Build Todo API
  Description: Learn FastAPI by building a complete REST API...
  Children: 3
```

---

#### `ltt project export`

Export a project to JSON file.

```bash
ltt project export proj-a1b2 \
  --output backup.json \
  --format json
```

**Options**:
- `--output, -o`: Output file path (default: `project.json`)
- `--format, -f`: Format: `json` or `jsonl` (default: `json`)

**Output**:
```
Exported to backup.json
```

---

### Ingestion

#### `ltt ingest project`

Import a complete project from JSON file.

```bash
# Dry run (validate without creating)
ltt ingest project my_project.json --dry-run

# Import for real
ltt ingest project my_project.json
```

**Options**:
- `--dry-run`: Validate structure without creating anything

**Dry Run Output**:
```
Dry run - no changes made
Would create: 42 tasks
Would create: 18 objectives
```

**Success Output**:
```
Imported project: proj-x1y2
  Tasks created: 42
  Objectives created: 18
```

**File Format**: See [SCHEMA-FOR-LLM-INGESTION.md](./SCHEMA-FOR-LLM-INGESTION.md)

---

### Task Management

#### `ltt task create`

Create a new task under an existing parent.

```bash
ltt task create "Implement Login" \
  --parent proj-a1b2.1 \
  --description "Create login endpoint" \
  --ac "- Accepts email/password\n- Returns JWT token" \
  --type task \
  --priority 0
```

**Options**:
- `--parent, -p`: Parent task ID (required)
- `--description, -d`: Task description
- `--ac`: Acceptance criteria
- `--type, -t`: Task type: `task`, `subtask`, `epic` (default: `task`)
- `--priority, -P`: Priority 0-4 (default: 2)

**Output**:
```
Created: proj-a1b2.1.3
```

---

#### `ltt task add-objective`

Add a learning objective to a task.

```bash
ltt task add-objective proj-a1b2.1 \
  "Implement REST endpoints in FastAPI" \
  --level apply
```

**Arguments**:
- `task_id`: Task to attach objective to
- `description`: Objective description

**Options**:
- `--level, -l`: Bloom level: `remember`, `understand`, `apply`, `analyze`, `evaluate`, `create` (default: `apply`)

**Output**:
```
Added objective: obj-abc123
```

---

### Content Management

#### `ltt content create`

Create a content item.

```bash
# From string
ltt content create \
  --type markdown \
  --body "# FastAPI Basics\n\nFastAPI is a modern Python web framework..."

# From file
ltt content create \
  --type markdown \
  --file path/to/tutorial.md
```

**Options**:
- `--type, -t`: Content type: `markdown`, `code`, `video_ref`, `external_link` (default: `markdown`)
- `--body, -b`: Content body (direct string)
- `--file, -f`: Read content from file

**Output**:
```
Created content: cnt-xyz123
```

---

#### `ltt content attach`

Attach content to a task.

```bash
ltt content attach cnt-xyz123 proj-a1b2.1
```

**Arguments**:
- `content_id`: Content to attach
- `task_id`: Task to attach to

**Output**:
```
Attached cnt-xyz123 to proj-a1b2.1
```

---

### Learner Management

#### `ltt learner create`

Create a new learner.

```bash
ltt learner create --metadata '{"name": "Alice", "cohort": "2024-01"}'
```

**Options**:
- `--metadata, -m`: JSON metadata (default: `{}`)

**Output**:
```
Created learner: learner-abc123
```

---

#### `ltt learner list`

List all learners.

```bash
ltt learner list --limit 50
```

**Options**:
- `--limit, -n`: Maximum learners to show (default: 20)

**Output**:
```
• learner-abc123
• learner-def456
• learner-ghi789
```

---

#### `ltt learner progress`

Show a learner's progress in a project.

```bash
ltt learner progress learner-abc123 proj-xyz789
```

**Output**:
```
Progress for learner-abc123 in proj-xyz789:
  Completed: 15/42
  Percentage: 35.7%
  In Progress: 3
  Blocked: 2
  Objectives: 8/18
```

---

### Database Operations

#### `ltt db init`

Initialize database schema (run migrations).

```bash
ltt db init
```

**Output**:
```
Running database migrations...
Database initialized successfully
```

---

## Common Workflows

### Creating a Project from Scratch

```bash
# 1. Create project
ltt project create "Build Todo API"

# 2. Add epic
ltt task create "Backend API" \
  --parent proj-a1b2 \
  --type epic

# 3. Add task
ltt task create "User Authentication" \
  --parent proj-a1b2.1 \
  --ac "- Users can register\n- Users can login" \
  --priority 0

# 4. Add subtask
ltt task create "Create login endpoint" \
  --parent proj-a1b2.1.1 \
  --type subtask \
  --ac "- POST /auth/login endpoint\n- Returns JWT token"

# 5. Add learning objectives
ltt task add-objective proj-a1b2.1.1 \
  "Implement JWT authentication" \
  --level apply
```

### Importing a Complete Project

```bash
# 1. Prepare JSON file (see SCHEMA-FOR-LLM-INGESTION.md)

# 2. Validate (dry run)
ltt ingest project my_project.json --dry-run

# 3. Check output
# If validation passes:
Would create: 42 tasks
Would create: 18 objectives

# 4. Import for real
ltt ingest project my_project.json

# Output:
Imported project: proj-x1y2
  Tasks created: 42
  Objectives created: 18
```

### Export and Backup

```bash
# Export to JSON
ltt project export proj-a1b2 --output backup.json

# Export to JSONL (one object per line)
ltt project export proj-a1b2 --output backup.jsonl --format jsonl
```

### Working with Content

```bash
# Create tutorial content
ltt content create \
  --type markdown \
  --file docs/fastapi-tutorial.md

# Output: cnt-abc123

# Attach to multiple tasks
ltt content attach cnt-abc123 proj-xyz.1.1
ltt content attach cnt-abc123 proj-xyz.1.2
ltt content attach cnt-abc123 proj-xyz.2.1
```

### Monitoring Learner Progress

```bash
# List all learners
ltt learner list

# Check specific learner's progress
ltt learner progress learner-abc123 proj-xyz789

# Output shows:
# - Tasks completed
# - Current in-progress tasks
# - Blocked tasks
# - Learning objectives achieved
```

---

## Environment Variables

### Database Configuration

```bash
# Set custom database URL
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/ltt"

# Default if not set:
# postgresql+asyncpg://ltt:ltt@localhost:5432/ltt
```

### Alembic Configuration

```bash
# Required for database migrations
export PYTHONPATH=src

# Run migrations manually
PYTHONPATH=src uv run alembic upgrade head
```

---

## File Paths

- **Project JSON files**: Can be anywhere, specify full/relative path
- **Content files**: Can be anywhere, read via `--file` option
- **Export output**: Defaults to current directory, customize with `--output`

---

## Error Handling

### Common Errors

**"Task not found"**
```bash
# Check task ID is correct
ltt project show proj-abc123

# List children of parent
ltt project show proj-abc123  # Shows children
```

**"Invalid project structure"**
```bash
# Use dry run to see validation errors
ltt ingest project my_project.json --dry-run

# Fix errors in JSON file, then re-run
```

**"Database connection failed"**
```bash
# Check PostgreSQL is running
docker-compose ps

# Start if needed
docker-compose up -d

# Verify connection
psql postgresql://ltt:ltt@localhost:5432/ltt -c "SELECT 1"
```

---

## Tips & Best Practices

### 1. Always Dry Run First
```bash
ltt ingest project new_project.json --dry-run
```
Validates structure without creating anything.

### 2. Export for Backup
```bash
ltt project export proj-abc123 --output backup-$(date +%Y%m%d).json
```
Version your project structures.

### 3. Use Descriptive Titles
- Good: "Implement JWT Authentication"
- Bad: "Auth" or "Task 3"

Titles are used for dependency resolution!

### 4. Structure Projects Thoughtfully
- **1 Project** = Full learning journey (weeks/months)
- **2-5 Epics** = Major features/milestones
- **3-8 Tasks per Epic** = Cohesive components
- **3-8 Subtasks per Task** = Atomic work items

### 5. Rich Acceptance Criteria
Every subtask should have testable acceptance criteria.
This is what determines if learners can proceed.

---

## Next Steps

1. **Create a project structure** using the schema guide
2. **Validate with dry run**: `ltt ingest project --dry-run`
3. **Import**: `ltt ingest project my_project.json`
4. **Create learners**: `ltt learner create`
5. **Use agent tools** (Phase 7) for runtime interactions

See [SCHEMA-FOR-LLM-INGESTION.md](./SCHEMA-FOR-LLM-INGESTION.md) for detailed schema guidance.
