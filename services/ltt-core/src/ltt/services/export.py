"""
Export service for exporting projects to JSON/JSONL.

Handles recursive serialization of project hierarchies.
"""

import json

from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import DependencyType, TaskType
from ltt.services.dependency_service import get_dependencies
from ltt.services.learning import get_objectives
from ltt.services.task_service import get_children, get_task


async def export_project(session: AsyncSession, project_id: str, format: str = "json") -> str:
    """
    Export a project to JSON or JSONL.

    Args:
        session: Database session
        project_id: Project to export
        format: Output format (json or jsonl)

    Returns:
        Serialized project as string

    Raises:
        ValueError: If format is unknown
        TaskNotFoundError: If project doesn't exist
    """
    project = await get_task(session, project_id)
    objectives = await get_objectives(session, project_id)

    data = {
        "title": project.title,
        "description": project.description,
        "learning_objectives": [
            {"level": o.level, "description": o.description} for o in objectives
        ],
        "content": project.content,
        "epics": [],
    }

    # Add narrative_context if present (primarily for projects)
    if project.narrative_context:
        data["narrative_context"] = project.narrative_context

    # Get epics (direct children)
    children = await get_children(session, project_id)
    for child in children:
        child_data = await export_task_tree(session, child.id)
        data["epics"].append(child_data)

    if format == "json":
        return json.dumps(data, indent=2)
    elif format == "jsonl":
        # Flatten to JSONL (one JSON object per line)
        lines = []
        lines.append(json.dumps({"type": "project", **data}))
        for epic in data["epics"]:
            lines.append(json.dumps({"type": "epic", **epic}))
        return "\n".join(lines)
    else:
        raise ValueError(f"Unknown format: {format}. Use 'json' or 'jsonl'")


async def export_task_tree(session: AsyncSession, task_id: str) -> dict:
    """
    Export a task and all its children recursively.

    Args:
        session: Database session
        task_id: Root task to export

    Returns:
        Nested dict structure
    """
    task = await get_task(session, task_id)
    objectives = await get_objectives(session, task_id)
    dependencies = await get_dependencies(session, task_id)

    # Build base data
    data = {
        "title": task.title,
        "description": task.description,
        "acceptance_criteria": task.acceptance_criteria,
        "learning_objectives": [
            {"level": o.level, "description": o.description} for o in objectives
        ],
        "priority": task.priority,
        "content": task.content,
    }

    # Add tutor_guidance if present
    if task.tutor_guidance:
        data["tutor_guidance"] = task.tutor_guidance

    # Add dependencies (export as titles for readability)
    # Note: We only export blocking dependencies, not parent_child (implicit in hierarchy)
    dep_titles = []
    for dep in dependencies:
        if dep.dependency_type == DependencyType.BLOCKS:
            dep_task = await get_task(session, dep.depends_on_id)
            dep_titles.append(dep_task.title)
    if dep_titles:
        data["dependencies"] = dep_titles

    # Get children recursively
    children = await get_children(session, task_id)
    if children:
        # Determine child key based on task type
        child_key = "tasks" if task.task_type == TaskType.EPIC else "subtasks"
        data[child_key] = []
        for child in children:
            child_data = await export_task_tree(session, child.id)
            data[child_key].append(child_data)

    return data
