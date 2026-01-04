"""
Ingestion service for importing projects from JSON files.

Handles recursive project structure creation with dependency resolution.
Uses LLM-based hierarchical summarization for tasks and epics.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import BloomLevel, DependencyType, TaskCreate, TaskType
from ltt.services.dependency_service import add_dependency
from ltt.services.learning import attach_objective
from ltt.services.learning.llm_summarization import (
    generate_epic_summary,
    generate_task_summary,
)
from ltt.services.task_service import create_task, update_task_summary

logger = logging.getLogger(__name__)


@dataclass
class ProjectContext:
    """Context passed down through the hierarchy for summarization."""

    project_title: str
    project_description: str
    project_narrative: str | None = None


@dataclass
class EpicContext:
    """Epic context for task summarization."""

    epic_title: str
    epic_description: str


@dataclass
class TaskWithSummary:
    """Task data enriched with its generated summary."""

    task_id: str
    title: str
    description: str
    summary: str | None = None


@dataclass
class IngestResult:
    """Result of an ingestion operation."""

    project_id: str
    task_count: int
    objective_count: int
    errors: list[str] = field(default_factory=list)


async def ingest_project_file(
    session: AsyncSession,
    file_path: Path,
    dry_run: bool = False,
    use_llm_summaries: bool = True,
) -> IngestResult:
    """
    Ingest a project from a JSON file.

    Args:
        session: Database session
        file_path: Path to JSON file
        dry_run: If True, validate without creating
        use_llm_summaries: If True, use LLM to generate hierarchical summaries

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

    # Create project context for summarization
    project_ctx = ProjectContext(
        project_title=data["title"],
        project_description=data.get("description", ""),
        project_narrative=data.get("narrative_context"),
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

    # Process epics (sequentially to maintain dependency order, but tasks within can be parallel)
    task_count = 1  # Count project itself
    for epic_data in data.get("epics", []):
        epic_count, epic_obj_count = await ingest_epic(
            session,
            epic_data,
            parent_id=project.id,
            project_id=project.id,
            dependency_map=dependency_map,
            project_ctx=project_ctx,
            use_llm_summaries=use_llm_summaries,
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
    project_ctx: ProjectContext,
    use_llm_summaries: bool = True,
) -> tuple[int, int]:
    """
    Recursively ingest an epic with its tasks.

    Args:
        session: Database session
        data: Epic data dict
        parent_id: Parent task ID
        project_id: Root project ID
        dependency_map: Title -> ID mapping for dependency resolution
        project_ctx: Project context for summarization
        use_llm_summaries: Whether to use LLM for summary generation

    Returns:
        (task_count, objective_count)
    """
    epic_ctx = EpicContext(
        epic_title=data["title"],
        epic_description=data.get("description", ""),
    )

    # Create epic (without summary initially)
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

    # Add dependencies (by title reference) - same as tasks
    for dep_title in data.get("dependencies", []):
        if dep_title in dependency_map:
            await add_dependency(session, epic.id, dependency_map[dep_title], DependencyType.BLOCKS)

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

    # Process tasks and collect info for epic summary
    task_count = 1  # Count the epic
    tasks_with_summaries: list[TaskWithSummary] = []

    # Process tasks sequentially (for dependency resolution)
    # but LLM calls within tasks can be parallel
    for task_data in data.get("tasks", []):
        count, obj_count_child, task_info = await ingest_task(
            session,
            task_data,
            parent_id=epic.id,
            project_id=project_id,
            dependency_map=dependency_map,
            project_ctx=project_ctx,
            epic_ctx=epic_ctx,
            use_llm_summaries=use_llm_summaries,
        )
        task_count += count
        obj_count += obj_count_child
        tasks_with_summaries.append(task_info)

    # Generate epic summary from task summaries using LLM
    if tasks_with_summaries and use_llm_summaries:
        try:
            # Build list of task dicts for LLM
            tasks_for_llm = [
                {
                    "title": t.title,
                    "description": t.description,
                    "summary": t.summary,
                }
                for t in tasks_with_summaries
            ]

            summary = await generate_epic_summary(
                epic_id=epic.id,
                epic_title=data["title"],
                epic_description=data.get("description", ""),
                tasks_with_summaries=tasks_for_llm,
                project_title=project_ctx.project_title,
                project_description=project_ctx.project_description,
                project_narrative=project_ctx.project_narrative,
            )
            await update_task_summary(session, epic.id, summary)
            logger.info(f"Generated LLM summary for epic: {data['title']}")
        except Exception as e:
            logger.warning(f"Failed to generate LLM summary for epic {data['title']}: {e}")
            # Fallback to simple summary
            simple_summary = "Tasks in this epic:\n" + "\n".join(
                f"- {t.title}: {t.description}" for t in tasks_with_summaries
            )
            await update_task_summary(session, epic.id, simple_summary)
    elif tasks_with_summaries:
        # Simple summary without LLM
        simple_summary = "Tasks in this epic:\n" + "\n".join(
            f"- {t.title}: {t.description}" for t in tasks_with_summaries
        )
        await update_task_summary(session, epic.id, simple_summary)

    return task_count, obj_count


async def ingest_task(
    session: AsyncSession,
    data: dict,
    parent_id: str,
    project_id: str,
    dependency_map: dict[str, str],
    project_ctx: ProjectContext,
    epic_ctx: EpicContext,
    use_llm_summaries: bool = True,
) -> tuple[int, int, TaskWithSummary]:
    """
    Recursively ingest a task with its subtasks.

    Args:
        session: Database session
        data: Task data dict
        parent_id: Parent task ID
        project_id: Root project ID
        dependency_map: Title -> ID mapping for dependency resolution
        project_ctx: Project context for summarization
        epic_ctx: Epic context for summarization
        use_llm_summaries: Whether to use LLM for summary generation

    Returns:
        (task_count, objective_count, task_info)
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
    subtask_infos: list[dict] = []

    for subtask_data in data.get("subtasks", []):
        count, obj_count_child, subtask_info = await ingest_task(
            session,
            subtask_data,
            parent_id=task.id,
            project_id=project_id,
            dependency_map=dependency_map,
            project_ctx=project_ctx,
            epic_ctx=epic_ctx,
            use_llm_summaries=use_llm_summaries,
        )
        task_count += count
        obj_count += obj_count_child
        subtask_infos.append({
            "title": subtask_info.title,
            "description": subtask_info.description,
        })

    # Generate task summary from subtasks using LLM (only for tasks with subtasks)
    task_summary: str | None = None
    if subtask_infos and has_subtasks and use_llm_summaries:
        try:
            task_summary = await generate_task_summary(
                task_id=task.id,
                task_title=data["title"],
                task_description=data.get("description", ""),
                acceptance_criteria=data.get("acceptance_criteria", ""),
                subtasks=subtask_infos,
                project_title=project_ctx.project_title,
                project_description=project_ctx.project_description,
                project_narrative=project_ctx.project_narrative,
                epic_title=epic_ctx.epic_title,
                epic_description=epic_ctx.epic_description,
            )
            await update_task_summary(session, task.id, task_summary)
            logger.info(f"Generated LLM summary for task: {data['title']}")
        except Exception as e:
            logger.warning(f"Failed to generate LLM summary for task {data['title']}: {e}")
            # Fallback to simple summary
            simple_summary = "Subtasks:\n" + "\n".join(
                f"- {s['title']}: {s['description']}" for s in subtask_infos
            )
            await update_task_summary(session, task.id, simple_summary)
            task_summary = simple_summary
    elif subtask_infos and has_subtasks:
        # Simple summary without LLM
        simple_summary = "Subtasks:\n" + "\n".join(
            f"- {s['title']}: {s['description']}" for s in subtask_infos
        )
        await update_task_summary(session, task.id, simple_summary)
        task_summary = simple_summary

    # Return task info for parent summarization
    task_info = TaskWithSummary(
        task_id=task.id,
        title=data["title"],
        description=data.get("description", ""),
        summary=task_summary,
    )

    return task_count, obj_count, task_info


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
