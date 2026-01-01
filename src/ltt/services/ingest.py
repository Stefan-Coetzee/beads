"""
Ingestion service for importing projects from JSON files.

Handles recursive project structure creation with dependency resolution.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import BloomLevel, DependencyType, TaskCreate, TaskType
from ltt.services.dependency_service import add_dependency
from ltt.services.learning import attach_objective
from ltt.services.task_service import create_task


@dataclass
class IngestResult:
    """Result of an ingestion operation."""

    project_id: str
    task_count: int
    objective_count: int
    errors: list[str]


async def ingest_project_file(
    session: AsyncSession, file_path: Path, dry_run: bool = False
) -> IngestResult:
    """
    Ingest a project from a JSON file.

    Args:
        session: Database session
        file_path: Path to JSON file
        dry_run: If True, validate without creating

    Returns:
        IngestResult with project_id and counts

    Raises:
        ValueError: If structure is invalid
        FileNotFoundError: If file doesn't exist
    """
    # Load and parse file
    with open(file_path) as f:
        data = json.load(f)

    # Validate structure
    errors = validate_project_structure(data)
    if errors and not dry_run:
        raise ValueError(f"Invalid project structure: {', '.join(errors)}")

    if dry_run:
        return IngestResult(
            project_id="(dry-run)",
            task_count=count_tasks(data),
            objective_count=count_objectives(data),
            errors=errors,
        )

    # Create project
    project = await create_task(
        session,
        TaskCreate(
            title=data["title"],
            description=data.get("description", ""),
            task_type=TaskType.PROJECT,
            content=data.get("content"),
            narrative_context=data.get("narrative_context"),
        ),
    )

    # Add project objectives
    obj_count = 0
    for obj in data.get("learning_objectives", []):
        await attach_objective(
            session,
            task_id=project.id,
            description=obj["description"],
            level=BloomLevel(obj.get("level", "apply")),
        )
        obj_count += 1

    # Track tasks by title for dependency resolution
    dependency_map: dict[str, str] = {data["title"]: project.id}

    # Process epics
    task_count = 1  # Count project itself
    for epic_data in data.get("epics", []):
        epic_count, epic_obj_count = await ingest_epic(
            session,
            epic_data,
            parent_id=project.id,
            project_id=project.id,
            dependency_map=dependency_map,
        )
        task_count += epic_count
        obj_count += epic_obj_count

    return IngestResult(
        project_id=project.id, task_count=task_count, objective_count=obj_count, errors=[]
    )


async def ingest_epic(
    session: AsyncSession,
    data: dict,
    parent_id: str,
    project_id: str,
    dependency_map: dict[str, str],
) -> tuple[int, int]:
    """
    Recursively ingest an epic with its tasks.

    Args:
        session: Database session
        data: Epic data dict
        parent_id: Parent task ID
        project_id: Root project ID
        dependency_map: Title -> ID mapping for dependency resolution

    Returns:
        (task_count, objective_count)
    """
    # Create epic
    epic = await create_task(
        session,
        TaskCreate(
            title=data["title"],
            description=data.get("description", ""),
            parent_id=parent_id,
            project_id=project_id,
            task_type=TaskType.EPIC,
            content=data.get("content"),
            tutor_guidance=data.get("tutor_guidance"),
        ),
    )

    # Track for dependency resolution
    dependency_map[data["title"]] = epic.id

    # Add objectives
    obj_count = 0
    for obj in data.get("learning_objectives", []):
        await attach_objective(
            session,
            task_id=epic.id,
            description=obj["description"],
            level=BloomLevel(obj.get("level", "apply")),
        )
        obj_count += 1

    # Process tasks
    task_count = 1  # Count the epic
    for task_data in data.get("tasks", []):
        count, obj_count_child = await ingest_task(
            session,
            task_data,
            parent_id=epic.id,
            project_id=project_id,
            dependency_map=dependency_map,
        )
        task_count += count
        obj_count += obj_count_child

    return task_count, obj_count


async def ingest_task(
    session: AsyncSession,
    data: dict,
    parent_id: str,
    project_id: str,
    dependency_map: dict[str, str],
) -> tuple[int, int]:
    """
    Recursively ingest a task with its subtasks.

    Args:
        session: Database session
        data: Task data dict
        parent_id: Parent task ID
        project_id: Root project ID
        dependency_map: Title -> ID mapping for dependency resolution

    Returns:
        (task_count, objective_count)
    """
    # Determine task type
    has_subtasks = bool(data.get("subtasks"))
    task_type = TaskType.TASK if has_subtasks else TaskType.SUBTASK

    # Create task
    task = await create_task(
        session,
        TaskCreate(
            title=data["title"],
            description=data.get("description", ""),
            acceptance_criteria=data.get("acceptance_criteria", ""),
            parent_id=parent_id,
            project_id=project_id,
            task_type=task_type,
            priority=data.get("priority", 2),
            content=data.get("content"),
            tutor_guidance=data.get("tutor_guidance"),
        ),
    )

    # Track for dependency resolution
    dependency_map[data["title"]] = task.id

    # Add objectives
    obj_count = 0
    for obj in data.get("learning_objectives", []):
        await attach_objective(
            session,
            task_id=task.id,
            description=obj["description"],
            level=BloomLevel(obj.get("level", "apply")),
        )
        obj_count += 1

    # Add dependencies (by title reference)
    for dep_title in data.get("dependencies", []):
        if dep_title in dependency_map:
            await add_dependency(session, task.id, dependency_map[dep_title], DependencyType.BLOCKS)

    # Process subtasks recursively
    task_count = 1
    for subtask_data in data.get("subtasks", []):
        count, obj_count_child = await ingest_task(
            session,
            subtask_data,
            parent_id=task.id,
            project_id=project_id,
            dependency_map=dependency_map,
        )
        task_count += count
        obj_count += obj_count_child

    return task_count, obj_count


def validate_project_structure(data: dict) -> list[str]:
    """
    Validate project structure.

    Returns list of error messages (empty if valid).
    """
    errors = []

    if not isinstance(data, dict):
        errors.append("Root must be an object")
        return errors

    if "title" not in data:
        errors.append("Project must have 'title' field")

    # Validate epics if present
    for i, epic in enumerate(data.get("epics", [])):
        if not isinstance(epic, dict):
            errors.append(f"Epic {i} must be an object")
            continue
        if "title" not in epic:
            errors.append(f"Epic {i} missing 'title'")

    return errors


def count_tasks(data: dict) -> int:
    """Count total tasks in project structure."""
    count = 1  # Count this node

    for epic in data.get("epics", []):
        count += count_tasks(epic)

    for task in data.get("tasks", []):
        count += count_tasks(task)

    for subtask in data.get("subtasks", []):
        count += count_tasks(subtask)

    return count


def count_objectives(data: dict) -> int:
    """Count total learning objectives in project structure."""
    count = len(data.get("learning_objectives", []))

    for epic in data.get("epics", []):
        count += count_objectives(epic)

    for task in data.get("tasks", []):
        count += count_objectives(task)

    for subtask in data.get("subtasks", []):
        count += count_objectives(subtask)

    return count
