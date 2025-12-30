# Admin CLI Module

> Project setup, ingestion, and administrative operations.

## Overview

This module provides the **admin interface** for:
- Creating and managing projects
- Ingesting project structures from files
- Versioning projects
- Bulk operations
- Export/backup

### Separation from Agent Tools

| Admin CLI | Agent Tools |
|-----------|-------------|
| Project setup | Runtime operations |
| Used by instructors/system | Used by LLM agents |
| Full access to all projects | Scoped to learner's data |
| Create/delete operations | Read + submit operations |

---

## 1. CLI Structure

```bash
ltt                          # Learning Task Tracker CLI
├── project                  # Project management
│   ├── create               # Create new project
│   ├── list                 # List projects
│   ├── show                 # Show project details
│   ├── delete               # Delete project
│   ├── version              # Version management
│   └── export               # Export project
├── ingest                   # Import from files
│   ├── epic                 # Ingest epic from file
│   └── project              # Ingest full project
├── task                     # Task management
│   ├── create               # Create task
│   ├── update               # Update task
│   ├── delete               # Delete task
│   └── move                 # Move task to new parent
├── content                  # Content management
│   ├── create               # Create content
│   ├── list                 # List content
│   └── attach               # Attach to task
├── learner                  # Learner management
│   ├── create               # Create learner
│   ├── list                 # List learners
│   └── progress             # Show progress
└── db                       # Database operations
    ├── init                 # Initialize database
    ├── migrate              # Run migrations
    └── backup               # Backup database
```

---

## 2. Implementation with Typer

```python
import typer
from typing import Optional
from pathlib import Path
import json

app = typer.Typer(name="ltt", help="Learning Task Tracker Admin CLI")

# ─────────────────────────────────────────────────────────────
# Project Commands
# ─────────────────────────────────────────────────────────────

project_app = typer.Typer(help="Project management")
app.add_typer(project_app, name="project")


@project_app.command("create")
def project_create(
    title: str = typer.Argument(..., help="Project title"),
    description: str = typer.Option("", "--description", "-d", help="Project description"),
    prefix: str = typer.Option("proj", "--prefix", "-p", help="ID prefix")
):
    """Create a new project."""
    from ltt.services.task import create_task
    from ltt.models import TaskCreate, TaskType

    with get_db_session() as db:
        project = create_task(
            db,
            TaskCreate(
                title=title,
                description=description,
                task_type=TaskType.PROJECT,
            ),
            actor="admin"
        )
        typer.echo(f"Created project: {project.id}")
        typer.echo(f"  Title: {project.title}")


@project_app.command("list")
def project_list(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum projects to show")
):
    """List all projects."""
    from ltt.services.task import list_tasks
    from ltt.models import TaskType

    with get_db_session() as db:
        projects = list_tasks(db, task_type=TaskType.PROJECT, limit=limit)

        if not projects:
            typer.echo("No projects found.")
            return

        for p in projects:
            status_icon = "✓" if p.status == "closed" else "○"
            typer.echo(f"{status_icon} {p.id}: {p.title}")


@project_app.command("show")
def project_show(
    project_id: str = typer.Argument(..., help="Project ID")
):
    """Show project details."""
    from ltt.services.task import get_task_detail

    with get_db_session() as db:
        project = get_task_detail(db, project_id)

        typer.echo(f"Project: {project.id}")
        typer.echo(f"  Title: {project.title}")
        typer.echo(f"  Status: {project.status}")
        typer.echo(f"  Description: {project.description[:200]}...")
        typer.echo(f"  Children: {len(project.children)}")


@project_app.command("export")
def project_export(
    project_id: str = typer.Argument(..., help="Project ID"),
    output: Path = typer.Option("project.json", "--output", "-o", help="Output file"),
    format: str = typer.Option("json", "--format", "-f", help="Format: json, jsonl")
):
    """Export a project to file."""
    from ltt.services.export import export_project

    with get_db_session() as db:
        data = export_project(db, project_id, format=format)

        with open(output, "w") as f:
            f.write(data)

        typer.echo(f"Exported to {output}")


# ─────────────────────────────────────────────────────────────
# Ingest Commands
# ─────────────────────────────────────────────────────────────

ingest_app = typer.Typer(help="Import from files")
app.add_typer(ingest_app, name="ingest")


@ingest_app.command("project")
def ingest_project(
    file: Path = typer.Argument(..., help="JSON/JSONL file to import"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without importing")
):
    """
    Ingest a complete project from file.

    Expects structure with project, epics, tasks, subtasks.
    """
    from ltt.services.ingest import ingest_project_file

    with get_db_session() as db:
        result = ingest_project_file(db, file, dry_run=dry_run)

        if dry_run:
            typer.echo("Dry run - no changes made")
            typer.echo(f"Would create: {result.task_count} tasks")
            if result.errors:
                typer.echo(f"Errors: {len(result.errors)}")
                for e in result.errors:
                    typer.echo(f"  - {e}")
        else:
            typer.echo(f"Imported project: {result.project_id}")
            typer.echo(f"  Tasks created: {result.task_count}")


@ingest_app.command("epic")
def ingest_epic(
    file: Path = typer.Argument(..., help="JSON/JSONL file to import"),
    project_id: str = typer.Option(..., "--project", "-p", help="Target project ID")
):
    """
    Ingest an epic into an existing project.
    """
    from ltt.services.ingest import ingest_epic_file

    with get_db_session() as db:
        result = ingest_epic_file(db, file, project_id)

        typer.echo(f"Imported epic: {result.epic_id}")
        typer.echo(f"  Tasks created: {result.task_count}")


# ─────────────────────────────────────────────────────────────
# Task Commands
# ─────────────────────────────────────────────────────────────

task_app = typer.Typer(help="Task management")
app.add_typer(task_app, name="task")


@task_app.command("create")
def task_create(
    title: str = typer.Argument(..., help="Task title"),
    parent_id: str = typer.Option(..., "--parent", "-p", help="Parent task ID"),
    description: str = typer.Option("", "--description", "-d"),
    acceptance_criteria: str = typer.Option("", "--ac"),
    task_type: str = typer.Option("task", "--type", "-t", help="task, subtask, epic"),
    priority: int = typer.Option(2, "--priority", "-P", help="0-4")
):
    """Create a new task."""
    from ltt.services.task import create_task
    from ltt.models import TaskCreate, TaskType

    with get_db_session() as db:
        task = create_task(
            db,
            TaskCreate(
                title=title,
                parent_id=parent_id,
                description=description,
                acceptance_criteria=acceptance_criteria,
                task_type=TaskType(task_type),
                priority=priority,
            ),
            actor="admin"
        )
        typer.echo(f"Created: {task.id}")


@task_app.command("add-objective")
def task_add_objective(
    task_id: str = typer.Argument(..., help="Task ID"),
    description: str = typer.Argument(..., help="Objective description"),
    level: str = typer.Option("apply", "--level", "-l", help="Bloom level")
):
    """Add a learning objective to a task."""
    from ltt.services.learning import attach_objective
    from ltt.models import BloomLevel

    with get_db_session() as db:
        obj = attach_objective(
            db,
            task_id=task_id,
            description=description,
            level=BloomLevel(level)
        )
        typer.echo(f"Added objective: {obj.id}")


# ─────────────────────────────────────────────────────────────
# Content Commands
# ─────────────────────────────────────────────────────────────

content_app = typer.Typer(help="Content management")
app.add_typer(content_app, name="content")


@content_app.command("create")
def content_create(
    content_type: str = typer.Option("markdown", "--type", "-t"),
    body: str = typer.Option(None, "--body", "-b", help="Content body"),
    file: Path = typer.Option(None, "--file", "-f", help="Read from file")
):
    """Create content item."""
    from ltt.services.content import create_content
    from ltt.models import ContentType

    if file:
        body = file.read_text()
    elif not body:
        typer.echo("Provide --body or --file")
        raise typer.Exit(1)

    with get_db_session() as db:
        content = create_content(
            db,
            content_type=ContentType(content_type),
            body=body
        )
        typer.echo(f"Created content: {content.id}")


@content_app.command("attach")
def content_attach(
    content_id: str = typer.Argument(..., help="Content ID"),
    task_id: str = typer.Argument(..., help="Task ID")
):
    """Attach content to a task."""
    from ltt.services.content import attach_content_to_task

    with get_db_session() as db:
        attach_content_to_task(db, content_id, task_id)
        typer.echo(f"Attached {content_id} to {task_id}")


# ─────────────────────────────────────────────────────────────
# Database Commands
# ─────────────────────────────────────────────────────────────

db_app = typer.Typer(help="Database operations")
app.add_typer(db_app, name="db")


@db_app.command("init")
def db_init():
    """Initialize the database."""
    from ltt.db import init_database

    init_database()
    typer.echo("Database initialized")


@db_app.command("migrate")
def db_migrate():
    """Run database migrations."""
    from ltt.db import run_migrations

    run_migrations()
    typer.echo("Migrations complete")


if __name__ == "__main__":
    app()
```

---

## 3. Ingestion Format

### Project JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Project",
  "type": "object",
  "required": ["title"],
  "properties": {
    "title": {"type": "string"},
    "description": {"type": "string"},
    "learning_objectives": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "level": {"enum": ["remember", "understand", "apply", "analyze", "evaluate", "create"]},
          "description": {"type": "string"}
        }
      }
    },
    "content": {"type": "string"},
    "epics": {
      "type": "array",
      "items": {"$ref": "#/definitions/Epic"}
    }
  },
  "definitions": {
    "Epic": {
      "type": "object",
      "required": ["title"],
      "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "learning_objectives": {"type": "array"},
        "content": {"type": "string"},
        "tasks": {
          "type": "array",
          "items": {"$ref": "#/definitions/Task"}
        }
      }
    },
    "Task": {
      "type": "object",
      "required": ["title"],
      "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "acceptance_criteria": {"type": "string"},
        "learning_objectives": {"type": "array"},
        "content": {"type": "string"},
        "priority": {"type": "integer", "minimum": 0, "maximum": 4},
        "dependencies": {"type": "array", "items": {"type": "string"}},
        "subtasks": {
          "type": "array",
          "items": {"$ref": "#/definitions/Task"}
        }
      }
    }
  }
}
```

### Example Project File

```json
{
  "title": "Build E-commerce Site",
  "description": "Complete e-commerce project with FastAPI backend and React frontend",
  "learning_objectives": [
    {"level": "create", "description": "Build a full-stack web application"},
    {"level": "apply", "description": "Apply REST API design principles"}
  ],
  "epics": [
    {
      "title": "Build FastAPI Backend",
      "description": "Create a complete REST API backend",
      "learning_objectives": [
        {"level": "apply", "description": "Build REST APIs with FastAPI"}
      ],
      "tasks": [
        {
          "title": "Set up project structure",
          "description": "Initialize FastAPI project with proper directory structure",
          "acceptance_criteria": "- Project runs with `uvicorn main:app`\n- /health returns 200",
          "learning_objectives": [
            {"level": "remember", "description": "Recall FastAPI project structure"}
          ],
          "priority": 0,
          "subtasks": [
            {
              "title": "Create main.py",
              "description": "Create the main FastAPI application file",
              "acceptance_criteria": "- FastAPI app instance created\n- Basic route defined",
              "learning_objectives": [
                {"level": "apply", "description": "Create a FastAPI application instance"}
              ]
            }
          ]
        },
        {
          "title": "Create user endpoints",
          "description": "Implement CRUD operations for users",
          "dependencies": ["Set up project structure"],
          "subtasks": [
            {
              "title": "Create GET /users endpoint",
              "acceptance_criteria": "- Returns list of users as JSON\n- Pagination supported"
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 4. Ingestion Service

```python
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import json


@dataclass
class IngestResult:
    """Result of an ingestion operation."""
    project_id: str
    task_count: int
    objective_count: int
    errors: List[str]


async def ingest_project_file(
    db,
    file_path: Path,
    dry_run: bool = False
) -> IngestResult:
    """
    Ingest a project from a JSON file.
    """
    # 1. Load and validate file
    with open(file_path) as f:
        data = json.load(f)

    errors = validate_project_structure(data)
    if errors and not dry_run:
        raise ValueError(f"Invalid project structure: {errors}")

    if dry_run:
        return IngestResult(
            project_id="(dry-run)",
            task_count=count_tasks(data),
            objective_count=count_objectives(data),
            errors=errors
        )

    # 2. Create project
    project = await create_task(
        db,
        TaskCreate(
            title=data["title"],
            description=data.get("description", ""),
            task_type=TaskType.PROJECT,
        ),
        actor="ingest"
    )

    # 3. Add project objectives
    for obj in data.get("learning_objectives", []):
        await attach_objective(
            db,
            task_id=project.id,
            description=obj["description"],
            level=BloomLevel(obj.get("level", "apply"))
        )

    # 4. Process epics
    task_count = 0
    for epic_data in data.get("epics", []):
        epic_result = await ingest_epic(
            db,
            epic_data,
            parent_id=project.id,
            project_id=project.id
        )
        task_count += epic_result

    return IngestResult(
        project_id=project.id,
        task_count=task_count + 1,  # +1 for project itself
        objective_count=count_objectives(data),
        errors=[]
    )


async def ingest_epic(
    db,
    data: dict,
    parent_id: str,
    project_id: str,
    dependency_map: Optional[dict] = None
) -> int:
    """
    Recursively ingest an epic with its tasks.
    """
    if dependency_map is None:
        dependency_map = {}

    # Create epic
    epic = await create_task(
        db,
        TaskCreate(
            title=data["title"],
            description=data.get("description", ""),
            parent_id=parent_id,
            project_id=project_id,
            task_type=TaskType.EPIC,
            content=data.get("content"),
        ),
        actor="ingest"
    )

    # Track for dependency resolution
    dependency_map[data["title"]] = epic.id

    # Add objectives
    for obj in data.get("learning_objectives", []):
        await attach_objective(
            db,
            task_id=epic.id,
            description=obj["description"],
            level=BloomLevel(obj.get("level", "apply"))
        )

    # Process tasks
    task_count = 1  # Count the epic
    for task_data in data.get("tasks", []):
        count = await ingest_task(
            db,
            task_data,
            parent_id=epic.id,
            project_id=project_id,
            dependency_map=dependency_map
        )
        task_count += count

    return task_count


async def ingest_task(
    db,
    data: dict,
    parent_id: str,
    project_id: str,
    dependency_map: dict
) -> int:
    """
    Recursively ingest a task with its subtasks.
    """
    # Determine task type
    has_subtasks = bool(data.get("subtasks"))
    task_type = TaskType.TASK if has_subtasks else TaskType.SUBTASK

    # Create task
    task = await create_task(
        db,
        TaskCreate(
            title=data["title"],
            description=data.get("description", ""),
            acceptance_criteria=data.get("acceptance_criteria", ""),
            parent_id=parent_id,
            project_id=project_id,
            task_type=task_type,
            priority=data.get("priority", 2),
            content=data.get("content"),
        ),
        actor="ingest"
    )

    # Track for dependency resolution
    dependency_map[data["title"]] = task.id

    # Add objectives
    for obj in data.get("learning_objectives", []):
        await attach_objective(
            db,
            task_id=task.id,
            description=obj["description"],
            level=BloomLevel(obj.get("level", "apply"))
        )

    # Add dependencies (by title reference)
    for dep_title in data.get("dependencies", []):
        if dep_title in dependency_map:
            await add_dependency(
                db,
                task_id=task.id,
                depends_on_id=dependency_map[dep_title],
                dependency_type=DependencyType.BLOCKS,
                actor="ingest"
            )

    # Process subtasks
    task_count = 1
    for subtask_data in data.get("subtasks", []):
        count = await ingest_task(
            db,
            subtask_data,
            parent_id=task.id,
            project_id=project_id,
            dependency_map=dependency_map
        )
        task_count += count

    return task_count
```

---

## 5. Export Service

```python
async def export_project(
    db,
    project_id: str,
    format: str = "json"
) -> str:
    """
    Export a project to JSON or JSONL.
    """
    project = await get_task_detail(db, project_id)
    objectives = await get_objectives(db, project_id)

    data = {
        "title": project.title,
        "description": project.description,
        "learning_objectives": [
            {"level": o.level, "description": o.description}
            for o in objectives
        ],
        "epics": []
    }

    # Get epics (direct children)
    epics = await get_children(db, project_id)
    for epic in epics:
        epic_data = await export_task_tree(db, epic.id)
        data["epics"].append(epic_data)

    if format == "json":
        return json.dumps(data, indent=2)
    elif format == "jsonl":
        lines = []
        lines.append(json.dumps({"type": "project", **data}))
        # Flatten to JSONL
        for epic in data["epics"]:
            lines.append(json.dumps({"type": "epic", **epic}))
        return "\n".join(lines)
    else:
        raise ValueError(f"Unknown format: {format}")


async def export_task_tree(db, task_id: str) -> dict:
    """Export a task and all its children recursively."""
    task = await get_task_detail(db, task_id)
    objectives = await get_objectives(db, task_id)

    data = {
        "title": task.title,
        "description": task.description,
        "acceptance_criteria": task.acceptance_criteria,
        "learning_objectives": [
            {"level": o.level, "description": o.description}
            for o in objectives
        ],
        "priority": task.priority,
        "content": task.content,
    }

    # Get children
    children = await get_children(db, task_id)
    if children:
        child_key = "tasks" if task.task_type == "epic" else "subtasks"
        data[child_key] = []
        for child in children:
            child_data = await export_task_tree(db, child.id)
            data[child_key].append(child_data)

    return data
```

---

## 6. File Structure

```
src/ltt/
├── cli/
│   ├── __init__.py
│   ├── main.py           # Typer app entry point
│   ├── project.py        # Project commands
│   ├── ingest.py         # Ingest commands
│   ├── task.py           # Task commands
│   ├── content.py        # Content commands
│   └── db.py             # Database commands
├── services/
│   ├── ingest.py         # Ingestion service
│   └── export.py         # Export service
```

---

## 7. Testing Requirements

```python
class TestIngestion:
    def test_ingest_valid_project(self):
        """Full project ingests correctly."""
        ...

    def test_ingest_resolves_dependencies(self):
        """Dependencies by title are resolved to IDs."""
        ...

    def test_dry_run_no_changes(self):
        """Dry run validates without changes."""
        ...

    def test_invalid_structure_fails(self):
        """Invalid JSON structure raises error."""
        ...


class TestExport:
    def test_export_roundtrip(self):
        """Export then import produces same structure."""
        ...
```
