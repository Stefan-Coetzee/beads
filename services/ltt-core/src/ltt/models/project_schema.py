"""
Pydantic models for validating project ingestion JSON.

These models define the expected shape of project JSON files at each level
of the hierarchy. They are the source of truth for what the ingestion
pipeline accepts.

Usage:
    from ltt.models.project_schema import ProjectSchema
    project = ProjectSchema.model_validate(json.load(open("project.json")))
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BloomLevel(StrEnum):
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class SubtaskType(StrEnum):
    EXERCISE = "exercise"
    CONVERSATIONAL = "conversational"


class TeachingStyle(StrEnum):
    SOCRATIC = "socratic"
    DIRECT = "direct"
    GUIDED = "guided"


class EncouragementLevel(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    MINIMAL = "minimal"


# ---------------------------------------------------------------------------
# Shared components
# ---------------------------------------------------------------------------


class LearningObjective(BaseModel):
    level: BloomLevel
    description: str = Field(..., min_length=1)


class TutorGuidance(BaseModel):
    """Per-subtask tutor hints. All fields optional — different subtask types
    use different subsets."""

    teaching_approach: str | None = None
    discussion_prompts: list[str] | None = None
    common_mistakes: list[str] | None = None
    hints_to_give: list[str] | None = None
    answer_rationale: str | None = None


class TutorConfig(BaseModel):
    """Project-level tutor behaviour. Sets defaults for the whole project;
    subtask-level ``tutor_guidance`` overrides for specific situations."""

    persona: str | None = None
    teaching_style: TeachingStyle | None = None
    encouragement_level: EncouragementLevel | None = None


# ---------------------------------------------------------------------------
# Hierarchy levels (bottom-up)
# ---------------------------------------------------------------------------


class SubtaskSchema(BaseModel):
    """Atomic work item — the leaf of the hierarchy."""

    title: str = Field(..., min_length=1)
    subtask_type: SubtaskType = SubtaskType.EXERCISE
    description: str = ""
    acceptance_criteria: str = ""
    learning_objectives: list[LearningObjective] = Field(default_factory=list)
    estimated_minutes: int | None = Field(default=None, ge=0)
    content: str | None = None
    tutor_guidance: TutorGuidance | None = None
    dependencies: list[str] = Field(default_factory=list)

    # Nested subtasks (rarely used)
    subtasks: list[SubtaskSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def exercise_needs_acceptance_criteria(self) -> SubtaskSchema:
        if self.subtask_type == SubtaskType.EXERCISE and not self.acceptance_criteria:
            # Warn but don't fail — some exercise subtasks may legitimately
            # omit AC if they're trivial. The validator can flag this.
            pass
        return self


class TaskSchema(BaseModel):
    """Cohesive unit of work — groups subtasks under one deliverable."""

    title: str = Field(..., min_length=1)
    description: str = ""
    acceptance_criteria: str = ""
    learning_objectives: list[LearningObjective] = Field(default_factory=list)
    estimated_minutes: int | None = Field(default=None, ge=0)
    priority: int = Field(default=2, ge=0, le=4)
    max_grade: float | None = Field(default=None, ge=0)
    content: str | None = None
    tutor_guidance: TutorGuidance | None = None
    dependencies: list[str] = Field(default_factory=list)
    subtasks: list[SubtaskSchema] = Field(default_factory=list)


class EpicSchema(BaseModel):
    """Major feature area or milestone — groups tasks into chapters."""

    title: str = Field(..., min_length=1)
    description: str = ""
    learning_objectives: list[LearningObjective] = Field(default_factory=list)
    estimated_minutes: int | None = Field(default=None, ge=0)
    priority: int = Field(default=2, ge=0, le=4)
    content: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    tasks: list[TaskSchema] = Field(default_factory=list)


class ProjectSchema(BaseModel):
    """Root project — the top of the hierarchy.

    Validate a project JSON file::

        import json
        from ltt.models.project_schema import ProjectSchema

        data = json.load(open("project.json"))
        project = ProjectSchema.model_validate(data)
    """

    # Stable identity and versioning
    project_id: str = Field(
        ...,
        min_length=3,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
    )
    version: int = Field(default=1, ge=1)
    version_tag: str | None = Field(default=None, max_length=100)

    title: str = Field(..., min_length=1)
    description: str = ""

    # Narrative framing
    narrative: bool = False
    narrative_context: str | None = None

    # Workspace
    workspace_type: Literal["sql", "python", "cybersecurity"] | None = None

    # Project-level tutor behaviour
    tutor_config: TutorConfig | None = None
    # Legacy field — maps to tutor_config.persona on ingest
    tutor_persona: str | None = None

    # Learning
    learning_objectives: list[LearningObjective] = Field(default_factory=list)
    content: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=0)

    # Submission requirement (project-level override)
    requires_submission: bool | None = None

    # Children
    epics: list[EpicSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def narrative_requires_context(self) -> ProjectSchema:
        if self.narrative and not self.narrative_context:
            raise ValueError("narrative_context is required when narrative is true")
        return self
