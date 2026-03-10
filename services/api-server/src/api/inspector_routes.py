"""
LLM Inspector — debug endpoints for the tutor agent.

1. ``/inspector/{project_id}`` — system prompt + context for every leaf task
2. ``/memory/{learner_id}`` — learner memory (profile + global/project observations)

Gated behind DEBUG=true.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.database import get_session_factory
from api.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])


# =============================================================================
# Response models
# =============================================================================


class InspectorObjective(BaseModel):
    level: str
    description: str


class InspectorTask(BaseModel):
    id: str
    title: str
    description: str | None = None
    task_type: str
    subtask_type: str | None = None
    acceptance_criteria: str | None = None
    content: str | None = None
    tutor_guidance: dict[str, Any] | None = None
    learning_objectives: list[InspectorObjective] = []


class InspectorEpic(BaseModel):
    id: str
    title: str
    description: str | None = None


class InspectorProgress(BaseModel):
    completed: int
    total: int
    percentage: float
    in_progress: int = 1
    blocked: int = 0


class InspectorStep(BaseModel):
    step_number: int
    breadcrumb: list[str]
    task: InspectorTask
    epic: InspectorEpic | None = None
    progress: InspectorProgress
    system_prompt: str
    tool_results: dict[str, Any] = Field(default_factory=dict)


class InspectorProject(BaseModel):
    id: str
    title: str
    description: str | None = None
    narrative_context: str | None = None
    workspace_type: str | None = None


class InspectorResponse(BaseModel):
    project: InspectorProject
    total_steps: int
    steps: list[InspectorStep]


# =============================================================================
# Endpoint
# =============================================================================


@router.get("/inspector/{project_id}", response_model=InspectorResponse)
async def get_inspector_data(project_id: str) -> InspectorResponse:
    """Return the full system prompt and tool context for every leaf task in a project."""

    if not get_settings().debug:
        raise HTTPException(status_code=404, detail="Not found")

    # Lazy imports — only needed when debug is on
    from agent.prompts import build_system_prompt
    from ltt.services.learning.objectives import get_objectives
    from ltt.services.task_service import TaskNotFoundError, get_ancestors, get_children, get_task

    session_factory = get_session_factory()

    async with session_factory() as session:
        # 1. Load project root
        try:
            project = await get_task(session, project_id)
        except TaskNotFoundError:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        # 2. Depth-first walk — collect all leaf nodes with breadcrumbs
        leaves: list[tuple[Any, list[str]]] = []

        async def walk(task_id: str, breadcrumb: list[str]) -> None:
            children = await get_children(session, task_id, recursive=False)
            children.sort(key=lambda t: (t.priority, t.id))
            if not children:
                task = await get_task(session, task_id)
                leaves.append((task, list(breadcrumb)))
            else:
                for child in children:
                    await walk(child.id, breadcrumb + [child.title])

        await walk(project_id, [])
        total_steps = len(leaves)

        if total_steps == 0:
            return InspectorResponse(
                project=InspectorProject(
                    id=project.id,
                    title=project.title,
                    description=project.description,
                    narrative_context=project.narrative_context,
                    workspace_type=project.workspace_type,
                ),
                total_steps=0,
                steps=[],
            )

        # 3. Build each step
        steps: list[InspectorStep] = []

        for i, (task, breadcrumb) in enumerate(leaves):
            # Find epic in ancestors
            ancestors = await get_ancestors(session, task.id)
            epic: InspectorEpic | None = None
            for anc in ancestors:
                if hasattr(anc.task_type, "value"):
                    tt = anc.task_type.value
                else:
                    tt = str(anc.task_type)
                if tt == "epic":
                    epic = InspectorEpic(
                        id=anc.id, title=anc.title, description=anc.description
                    )
                    break

            # Learning objectives
            objectives = await get_objectives(session, task.id)
            obj_list = [
                {
                    "level": o.level.value if hasattr(o.level, "value") else str(o.level),
                    "description": o.description,
                }
                for o in objectives
            ]

            # Simulated progress
            progress = InspectorProgress(
                completed=i,
                total=total_steps,
                percentage=round(i / total_steps * 100, 1),
            )

            # Task type as string
            task_type_str = task.task_type.value if hasattr(task.task_type, "value") else str(task.task_type)
            subtask_type_str = task.subtask_type if task.subtask_type else None

            # System prompt — the exact same function the agent uses
            epic_dict = (
                {"id": epic.id, "title": epic.title, "description": epic.description}
                if epic
                else None
            )
            task_dict = {
                "task_id": task.id,
                "task_title": task.title,
                "task_type": task_type_str,
                "status": "in_progress",
                "acceptance_criteria": task.acceptance_criteria or "",
                "tutor_guidance": task.tutor_guidance,
                "learning_objectives": obj_list,
            }
            progress_dict = {
                "completed": progress.completed,
                "total": progress.total,
                "percentage": progress.percentage,
                "in_progress": progress.in_progress,
                "blocked": progress.blocked,
            }

            system_prompt = build_system_prompt(
                project_id=project.id,
                narrative_context=project.narrative_context,
                project_description=project.description,
                project_content=project.content,
                current_epic=epic_dict,
                current_task=task_dict,
                progress=progress_dict,
                workspace_type=project.workspace_type,
                custom_persona=getattr(project, "tutor_persona", None),
            )

            # Simulated start_task tool result (StartTaskContextOutput shape)
            tool_result = {
                "success": True,
                "task_id": task.id,
                "status": "in_progress",
                "message": f"Started task: {task.title}",
                "context": {
                    "task_id": task.id,
                    "title": task.title,
                    "task_type": task_type_str,
                    "status": "in_progress",
                    "description": task.description or "",
                    "acceptance_criteria": task.acceptance_criteria or "",
                    "content": task.content,
                    "narrative_context": task.narrative_context,
                    "learning_objectives": obj_list,
                    "tutor_guidance": task.tutor_guidance,
                },
            }

            steps.append(
                InspectorStep(
                    step_number=i,
                    breadcrumb=breadcrumb,
                    task=InspectorTask(
                        id=task.id,
                        title=task.title,
                        description=task.description,
                        task_type=task_type_str,
                        subtask_type=subtask_type_str,
                        acceptance_criteria=task.acceptance_criteria,
                        content=task.content,
                        tutor_guidance=task.tutor_guidance,
                        learning_objectives=[
                            InspectorObjective(**o) for o in obj_list
                        ],
                    ),
                    epic=epic,
                    progress=progress,
                    system_prompt=system_prompt,
                    tool_results={"start_task": tool_result},
                )
            )

        return InspectorResponse(
            project=InspectorProject(
                id=project.id,
                title=project.title,
                description=project.description,
                narrative_context=project.narrative_context,
                workspace_type=project.workspace_type,
            ),
            total_steps=total_steps,
            steps=steps,
        )


# =============================================================================
# Memory inspector
# =============================================================================


class MemoryProfileResponse(BaseModel):
    name: str | None = None
    programming_experience: str | None = None
    learning_style: str | None = None
    communication_preferences: str | None = None
    strengths: list[str] = []
    areas_for_growth: list[str] = []
    interests: list[str] = []
    background: str | None = None


class MemoryEntryResponse(BaseModel):
    text: str
    context: str | None = None
    source: str = "agent"


class MemoryResponse(BaseModel):
    learner_id: str
    project_slug: str | None = None
    profile: MemoryProfileResponse
    global_memories: list[MemoryEntryResponse]
    project_memories: list[MemoryEntryResponse]
    prompt_block: str


@router.get("/memory/{learner_id}", response_model=MemoryResponse)
async def get_learner_memory(
    learner_id: str,
    project_slug: str | None = Query(None, description="Project slug for project-scoped memories"),
) -> MemoryResponse:
    """Return the learner's stored memory (profile + observations).

    Shows exactly what the agent sees at the start of each session.
    """
    if not get_settings().debug:
        raise HTTPException(status_code=404, detail="Not found")

    from agent.memory.reader import format_memories_for_prompt
    from agent.memory.store import LearnerMemory

    from api.agents import get_store

    store = get_store()
    if store is None:
        raise HTTPException(
            status_code=503,
            detail="Memory store not initialised (no checkpoint DB configured)",
        )

    mem = LearnerMemory(store, learner_id, project_slug)

    profile = await mem.get_profile()
    global_memories = await mem.get_global_memories()
    project_memories = await mem.get_project_memories()

    prompt_block = format_memories_for_prompt(
        profile=profile,
        global_memories=global_memories,
        project_memories=project_memories,
        project_slug=project_slug,
    )

    return MemoryResponse(
        learner_id=learner_id,
        project_slug=project_slug,
        profile=MemoryProfileResponse(**profile.model_dump()),
        global_memories=[MemoryEntryResponse(**m.model_dump()) for m in global_memories],
        project_memories=[MemoryEntryResponse(**m.model_dump()) for m in project_memories],
        prompt_block=prompt_block,
    )
