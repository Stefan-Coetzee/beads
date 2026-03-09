"""
Ingestion service for importing projects from JSON files.

Handles recursive project structure creation with dependency resolution.
Uses LLM-based hierarchical summarization for tasks and epics.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import BloomLevel, DependencyType, TaskCreate, TaskType, WorkspaceType
from ltt.services.dependency_service import add_dependency
from ltt.services.learning import attach_objective
from ltt.services.learning.llm_summarization import (
    generate_epic_summary,
    generate_task_summary,
)
from ltt.services.task_service import create_task, get_project_by_slug, update_task_summary

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


async def ingest_project_data(
    session: AsyncSession,
    data: dict,
    dry_run: bool = False,
    use_llm_summaries: bool = True,
    require_slug: bool = False,
) -> IngestResult:
    """
    Ingest a project from an already-parsed dict.

    This is the core ingestion function used by both the CLI (via
    ``ingest_project_file``) and the REST endpoint.

    Args:
        session: Database session
        data: Parsed project JSON dict
        dry_run: If True, validate without persisting
        use_llm_summaries: If True, use LLM to generate hierarchical summaries
        require_slug: If True, ``project_id`` slug is mandatory (admin endpoint)

    Returns:
        IngestResult with project_id and counts

    Raises:
        ValueError: If structure is invalid (and not dry_run)
    """
    # Validate structure
    errors = validate_project_structure(data, require_slug=require_slug)
    if errors and not dry_run:
        raise ValueError(f"Invalid project structure: {'; '.join(errors)}")

    # Check for duplicate slug before any DB changes (also during dry_run)
    slug = data.get("project_id")
    version = data.get("version", 1)

    if slug:
        existing = await get_project_by_slug(session, slug, version)
        if existing:
            msg = (
                f"Project '{slug}' version {version} already exists "
                f"(internal ID: {existing.id}). "
                f"Bump the version number in your JSON to create a new version."
            )
            if dry_run:
                errors.append(msg)
            else:
                raise ValueError(msg)

        latest = await get_project_by_slug(session, slug)  # no version → latest
        if latest and version <= latest.version:
            msg = (
                f"Project '{slug}' already has version {latest.version}. "
                f"New version must be higher (got {version})."
            )
            if dry_run:
                errors.append(msg)
            else:
                raise ValueError(msg)

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

    # Parse workspace_type if provided
    workspace_type = None
    if "workspace_type" in data:
        try:
            workspace_type = WorkspaceType(data["workspace_type"])
        except ValueError:
            logger.warning(f"Invalid workspace_type: {data['workspace_type']}, defaulting to None")

    # Get tutor_persona if provided (custom system prompt persona)
    tutor_persona = data.get("tutor_persona")

    # Create project
    project = await create_task(
        session,
        TaskCreate(
            title=data["title"],
            description=data.get("description", ""),
            task_type=TaskType.PROJECT,
            content=data.get("content"),
            narrative_context=data.get("narrative_context"),
            requires_submission=data.get("requires_submission"),
            workspace_type=workspace_type,
            tutor_persona=tutor_persona,
            estimated_minutes=data.get("estimated_minutes"),
            version=data.get("version", 1),
            version_tag=data.get("version_tag"),
            narrative=data.get("narrative", False),
            tutor_config=data.get("tutor_config"),
            project_slug=data.get("project_id"),
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

    # Process epics (sequentially to maintain dependency order)
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

    return await ingest_project_data(
        session, data, dry_run=dry_run, use_llm_summaries=use_llm_summaries
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
            requires_submission=data.get("requires_submission"),
            estimated_minutes=data.get("estimated_minutes"),
            priority=data.get("priority", 2),
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
            requires_submission=data.get("requires_submission"),
            estimated_minutes=data.get("estimated_minutes"),
            subtask_type=data.get("subtask_type", "exercise"),
            max_grade=data.get("max_grade"),
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
        subtask_infos.append(
            {
                "title": subtask_info.title,
                "description": subtask_info.description,
            }
        )

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


VALID_BLOOM_LEVELS = {"remember", "understand", "apply", "analyze", "evaluate", "create"}
VALID_WORKSPACE_TYPES = {"sql", "python", "jupyter", "terminal", "mixed"}
VALID_SUBTASK_TYPES = {"exercise", "conversational"}


def validate_project_structure(data: dict, *, require_slug: bool = False) -> list[str]:
    """
    Validate project structure with descriptive, remedial error messages.

    Args:
        data: Parsed project JSON dict.
        require_slug: If True, ``project_id`` is required (admin endpoint).
            If False (default / CLI), a missing slug is tolerated.

    Returns list of error messages (empty if valid).
    Each message includes the exact location and a fix suggestion.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        errors.append("Root must be a JSON object, got " + type(data).__name__)
        return errors

    # ── Required fields ──────────────────────────────────────────────────
    if "title" not in data:
        errors.append('Project: missing required field "title"')

    if "project_id" in data:
        if not isinstance(data["project_id"], str):
            errors.append(
                f'Project: "project_id" must be a string, got {type(data["project_id"]).__name__}'
            )
        else:
            slug = data["project_id"]
            import re

            if not re.match(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$", slug):
                errors.append(
                    f'Project: "project_id" value "{slug}" is invalid — '
                    "must be 3–64 chars, lowercase alphanumeric + hyphens, "
                    "starting and ending with a letter or digit"
                )
    elif require_slug:
        errors.append(
            'Project: missing required field "project_id" — '
            'add a stable slug like "project_id": "my-project-slug"'
        )

    # ── Optional typed fields ────────────────────────────────────────────
    if "version" in data and (not isinstance(data["version"], int) or data["version"] < 1):
        errors.append(
            'Project: "version" must be a positive integer (got {!r})'.format(data["version"])
        )

    if "workspace_type" in data and data["workspace_type"] not in VALID_WORKSPACE_TYPES:
        errors.append(
            f'Project: "workspace_type" value "{data["workspace_type"]}" is invalid — '
            f"choose from: {', '.join(sorted(VALID_WORKSPACE_TYPES))}"
        )

    # ── Learning objectives ──────────────────────────────────────────────
    _validate_objectives(data.get("learning_objectives", []), "project", errors)

    # ── Collect all task titles for dependency validation ─────────────────
    all_titles: set[str] = set()
    _collect_titles(data, all_titles)

    # ── Epics ────────────────────────────────────────────────────────────
    for i, epic in enumerate(data.get("epics", [])):
        if not isinstance(epic, dict):
            errors.append(f"epics[{i}]: must be an object, got {type(epic).__name__}")
            continue
        _validate_epic(epic, i, all_titles, errors)

    return errors


def _validate_objectives(objectives: list, path: str, errors: list[str]) -> None:
    """Validate a list of learning objectives at the given path."""
    if not isinstance(objectives, list):
        errors.append(f'{path}: "learning_objectives" must be a list')
        return
    for j, obj in enumerate(objectives):
        if not isinstance(obj, dict):
            errors.append(f"{path}.learning_objectives[{j}]: must be an object")
            continue
        if "description" not in obj:
            errors.append(f'{path}.learning_objectives[{j}]: missing "description"')
        level = obj.get("level", "apply")
        if level not in VALID_BLOOM_LEVELS:
            errors.append(
                f'{path}.learning_objectives[{j}]: Bloom level "{level}" is invalid — '
                f"choose from: {', '.join(sorted(VALID_BLOOM_LEVELS))}"
            )


def _validate_epic(epic: dict, idx: int, all_titles: set[str], errors: list[str]) -> None:
    """Validate a single epic and its tasks."""
    path = f"epics[{idx}]"
    if "title" not in epic:
        errors.append(f'{path}: missing required field "title"')
    _validate_objectives(epic.get("learning_objectives", []), path, errors)
    _validate_dependencies(epic.get("dependencies", []), path, all_titles, errors)

    for j, task in enumerate(epic.get("tasks", [])):
        if not isinstance(task, dict):
            errors.append(f"{path}.tasks[{j}]: must be an object")
            continue
        _validate_task(task, f"{path}.tasks[{j}]", all_titles, errors)


def _validate_task(task: dict, path: str, all_titles: set[str], errors: list[str]) -> None:
    """Validate a single task/subtask recursively."""
    if "title" not in task:
        errors.append(f'{path}: missing required field "title"')
    _validate_objectives(task.get("learning_objectives", []), path, errors)
    _validate_dependencies(task.get("dependencies", []), path, all_titles, errors)

    if "subtask_type" in task and task["subtask_type"] not in VALID_SUBTASK_TYPES:
        errors.append(
            f'{path}: "subtask_type" value "{task["subtask_type"]}" is invalid — '
            f"choose from: {', '.join(sorted(VALID_SUBTASK_TYPES))}"
        )

    for k, sub in enumerate(task.get("subtasks", [])):
        if not isinstance(sub, dict):
            errors.append(f"{path}.subtasks[{k}]: must be an object")
            continue
        _validate_task(sub, f"{path}.subtasks[{k}]", all_titles, errors)


def _validate_dependencies(deps: list, path: str, all_titles: set[str], errors: list[str]) -> None:
    """Validate that dependency references exist within the project."""
    if not isinstance(deps, list):
        errors.append(f'{path}: "dependencies" must be a list of task title strings')
        return
    for k, dep in enumerate(deps):
        if not isinstance(dep, str):
            errors.append(
                f"{path}.dependencies[{k}]: must be a string (task title), got {type(dep).__name__}"
            )
        elif dep not in all_titles:
            errors.append(
                f'{path}.dependencies[{k}]: references "{dep}" which does not exist in this project — '
                "check spelling or add a task/epic with that exact title"
            )


def _collect_titles(data: dict, titles: set[str]) -> None:
    """Recursively collect all task/epic titles for dependency validation."""
    if "title" in data:
        titles.add(data["title"])
    for epic in data.get("epics", []):
        if isinstance(epic, dict):
            _collect_titles(epic, titles)
    for task in data.get("tasks", []):
        if isinstance(task, dict):
            _collect_titles(task, titles)
    for sub in data.get("subtasks", []):
        if isinstance(sub, dict):
            _collect_titles(sub, titles)


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
