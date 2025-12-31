"""
Main CLI entry point for Learning Task Tracker admin interface.

Usage:
    ltt project create "My Project"
    ltt ingest project path/to/project.json
    ltt project list
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import typer
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from ltt.models import BloomLevel, ContentType, TaskCreate, TaskType

# Main app
app = typer.Typer(name="ltt", help="Learning Task Tracker Admin CLI")


# ============================================================================
# Database Session Helper
# ============================================================================


@asynccontextmanager
async def get_async_session():
    """Get async database session."""
    # Get database URL from environment or use default
    import os

    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://ltt:ltt@localhost:5432/ltt")

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session


def run_async(coro):
    """Helper to run async functions from Typer commands."""
    return asyncio.run(coro)


# ============================================================================
# Project Commands
# ============================================================================

project_app = typer.Typer(help="Project management")
app.add_typer(project_app, name="project")


@project_app.command("create")
def project_create(
    title: str = typer.Argument(..., help="Project title"),
    description: str = typer.Option("", "--description", "-d", help="Project description"),
):
    """Create a new project."""
    from ltt.services.task_service import create_task

    async def _create():
        async with get_async_session() as session:
            project = await create_task(
                session,
                TaskCreate(
                    title=title,
                    description=description,
                    task_type=TaskType.PROJECT,
                ),
            )
            return project

    project = run_async(_create())
    typer.echo(f"Created project: {project.id}")
    typer.echo(f"  Title: {project.title}")


@project_app.command("list")
def project_list(limit: int = typer.Option(20, "--limit", "-n", help="Maximum projects to show")):
    """List all projects."""
    from sqlalchemy import select

    from ltt.models import TaskModel

    async def _list():
        async with get_async_session() as session:
            result = await session.execute(
                select(TaskModel).where(TaskModel.task_type == TaskType.PROJECT.value).limit(limit)
            )
            return result.scalars().all()

    projects = run_async(_list())

    if not projects:
        typer.echo("No projects found.")
        return

    for p in projects:
        typer.echo(f"○ {p.id}: {p.title}")


@project_app.command("show")
def project_show(project_id: str = typer.Argument(..., help="Project ID")):
    """Show project details."""
    from ltt.services.task_service import get_children, get_task

    async def _show():
        async with get_async_session() as session:
            project = await get_task(session, project_id)
            children = await get_children(session, project_id)
            return project, children

    project, children = run_async(_show())

    typer.echo(f"Project: {project.id}")
    typer.echo(f"  Title: {project.title}")
    typer.echo(f"  Description: {project.description[:200] if project.description else '(none)'}")
    typer.echo(f"  Children: {len(children)}")


@project_app.command("export")
def project_export(
    project_id: str = typer.Argument(..., help="Project ID"),
    output: Path = typer.Option("project.json", "--output", "-o", help="Output file"),
    format: str = typer.Option("json", "--format", "-f", help="Format: json, jsonl"),
):
    """Export a project to file."""
    from ltt.services.export import export_project

    async def _export():
        async with get_async_session() as session:
            return await export_project(session, project_id, format=format)

    data = run_async(_export())

    with open(output, "w") as f:
        f.write(data)

    typer.echo(f"Exported to {output}")


# ============================================================================
# Ingest Commands
# ============================================================================

ingest_app = typer.Typer(help="Import from files")
app.add_typer(ingest_app, name="ingest")


@ingest_app.command("project")
def ingest_project(
    file: Path = typer.Argument(..., help="JSON/JSONL file to import"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without importing"),
):
    """
    Ingest a complete project from file.

    Expects structure with project, epics, tasks, subtasks.
    """
    from ltt.services.ingest import ingest_project_file

    async def _ingest():
        async with get_async_session() as session:
            return await ingest_project_file(session, file, dry_run=dry_run)

    result = run_async(_ingest())

    if dry_run:
        typer.echo("Dry run - no changes made")
        typer.echo(f"Would create: {result.task_count} tasks")
        typer.echo(f"Would create: {result.objective_count} objectives")
        if result.errors:
            typer.echo(f"Errors: {len(result.errors)}")
            for e in result.errors:
                typer.echo(f"  - {e}")
    else:
        typer.echo(f"Imported project: {result.project_id}")
        typer.echo(f"  Tasks created: {result.task_count}")
        typer.echo(f"  Objectives created: {result.objective_count}")


# ============================================================================
# Task Commands
# ============================================================================

task_app = typer.Typer(help="Task management")
app.add_typer(task_app, name="task")


@task_app.command("create")
def task_create(
    title: str = typer.Argument(..., help="Task title"),
    parent_id: str = typer.Option(..., "--parent", "-p", help="Parent task ID"),
    description: str = typer.Option("", "--description", "-d"),
    acceptance_criteria: str = typer.Option("", "--ac"),
    task_type: str = typer.Option("task", "--type", "-t", help="task, subtask, epic"),
    priority: int = typer.Option(2, "--priority", "-P", help="0-4"),
):
    """Create a new task."""
    from ltt.services.task_service import create_task, get_task

    async def _create():
        async with get_async_session() as session:
            # Get parent to determine project_id
            parent = await get_task(session, parent_id)

            task = await create_task(
                session,
                TaskCreate(
                    title=title,
                    parent_id=parent_id,
                    project_id=parent.project_id,
                    description=description,
                    acceptance_criteria=acceptance_criteria,
                    task_type=TaskType(task_type),
                    priority=priority,
                ),
            )
            return task

    task = run_async(_create())
    typer.echo(f"Created: {task.id}")


@task_app.command("add-objective")
def task_add_objective(
    task_id: str = typer.Argument(..., help="Task ID"),
    description: str = typer.Argument(..., help="Objective description"),
    level: str = typer.Option("apply", "--level", "-l", help="Bloom level"),
):
    """Add a learning objective to a task."""
    from ltt.services.learning import attach_objective

    async def _add():
        async with get_async_session() as session:
            return await attach_objective(
                session, task_id=task_id, description=description, level=BloomLevel(level)
            )

    obj = run_async(_add())
    typer.echo(f"Added objective: {obj.id}")


# ============================================================================
# Content Commands
# ============================================================================

content_app = typer.Typer(help="Content management")
app.add_typer(content_app, name="content")


@content_app.command("create")
def content_create(
    content_type: str = typer.Option("markdown", "--type", "-t"),
    body: str = typer.Option(None, "--body", "-b", help="Content body"),
    file: Path = typer.Option(None, "--file", "-f", help="Read from file"),
):
    """Create content item."""
    from ltt.services.learning import create_content

    if file:
        body = file.read_text()
    elif not body:
        typer.echo("Provide --body or --file")
        raise typer.Exit(1)

    async def _create():
        async with get_async_session() as session:
            return await create_content(session, ContentType(content_type), body)

    content = run_async(_create())
    typer.echo(f"Created content: {content.id}")


@content_app.command("attach")
def content_attach(
    content_id: str = typer.Argument(..., help="Content ID"), task_id: str = typer.Argument(..., help="Task ID")
):
    """Attach content to a task."""
    from ltt.services.learning import attach_content_to_task

    async def _attach():
        async with get_async_session() as session:
            await attach_content_to_task(session, content_id, task_id)

    run_async(_attach())
    typer.echo(f"Attached {content_id} to {task_id}")


# ============================================================================
# Learner Commands
# ============================================================================

learner_app = typer.Typer(help="Learner management")
app.add_typer(learner_app, name="learner")


@learner_app.command("create")
def learner_create(
    metadata: str = typer.Option("{}", "--metadata", "-m", help="JSON metadata"),
):
    """Create a new learner."""
    from ltt.models import LearnerModel
    from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id

    async def _create():
        async with get_async_session() as session:
            learner_id = generate_entity_id(PREFIX_LEARNER)
            learner = LearnerModel(id=learner_id, learner_metadata=metadata)
            session.add(learner)
            await session.commit()
            await session.refresh(learner)
            return learner

    learner = run_async(_create())
    typer.echo(f"Created learner: {learner.id}")


@learner_app.command("list")
def learner_list(limit: int = typer.Option(20, "--limit", "-n")):
    """List all learners."""
    from sqlalchemy import select

    from ltt.models import LearnerModel

    async def _list():
        async with get_async_session() as session:
            result = await session.execute(select(LearnerModel).limit(limit))
            return result.scalars().all()

    learners = run_async(_list())

    if not learners:
        typer.echo("No learners found.")
        return

    for learner in learners:
        typer.echo(f"• {learner.id}")


@learner_app.command("progress")
def learner_progress(
    learner_id: str = typer.Argument(..., help="Learner ID"),
    project_id: str = typer.Argument(..., help="Project ID"),
):
    """Show learner progress in a project."""
    from ltt.services.learning import get_progress

    async def _progress():
        async with get_async_session() as session:
            return await get_progress(session, learner_id, project_id)

    progress = run_async(_progress())

    typer.echo(f"Progress for {learner_id} in {project_id}:")
    typer.echo(f"  Completed: {progress.completed_tasks}/{progress.total_tasks}")
    typer.echo(f"  Percentage: {progress.completion_percentage:.1f}%")
    typer.echo(f"  In Progress: {progress.in_progress_tasks}")
    typer.echo(f"  Blocked: {progress.blocked_tasks}")
    typer.echo(f"  Objectives: {progress.objectives_achieved}/{progress.total_objectives}")


# ============================================================================
# Database Commands
# ============================================================================

db_app = typer.Typer(help="Database operations")
app.add_typer(db_app, name="db")


@db_app.command("init")
def db_init():
    """Initialize the database (run migrations)."""
    import subprocess

    typer.echo("Running database migrations...")
    result = subprocess.run(["PYTHONPATH=src", "uv", "run", "alembic", "upgrade", "head"], capture_output=True)

    if result.returncode == 0:
        typer.echo("Database initialized successfully")
    else:
        typer.echo(f"Error: {result.stderr.decode()}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
