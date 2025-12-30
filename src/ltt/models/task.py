"""
Task models for the Learning Task Tracker.

Task is the core entity representing any work item: project, epic, task, or subtask.
This is a TEMPLATE LAYER entity - shared across learners. Per-learner status
is tracked in LearnerTaskProgress.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ARRAY, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class TaskType(str, Enum):
    """Type of task in the hierarchy."""

    PROJECT = "project"
    EPIC = "epic"
    TASK = "task"
    SUBTASK = "subtask"


class TaskStatus(str, Enum):
    """Task workflow status."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    CLOSED = "closed"


# ============================================================================
# Pydantic Models (for API/validation)
# ============================================================================


class TaskBase(BaseModel):
    """Base fields for task creation and updates."""

    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="")
    acceptance_criteria: str = Field(default="")
    notes: str = Field(default="")
    priority: int = Field(default=2, ge=0, le=4)
    task_type: TaskType = Field(default=TaskType.TASK)
    estimated_minutes: int | None = Field(default=None, ge=0)

    # Learning-specific fields
    content: str | None = Field(default=None, description="Inline learning content")
    content_refs: list[str] = Field(default_factory=list, description="References to content IDs")


class TaskCreate(TaskBase):
    """Schema for creating a new task."""

    parent_id: str | None = Field(default=None, description="Parent task ID for hierarchy")
    project_id: str | None = Field(
        default=None,
        description="Project ID. Required for non-project tasks. Auto-set for projects.",
    )

    # Optional: provide a custom ID (otherwise generated)
    id: str | None = Field(default=None, pattern=r"^[a-z0-9\-\.]+$")


class TaskUpdate(BaseModel):
    """Schema for updating an existing task. All fields optional."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    acceptance_criteria: str | None = None
    notes: str | None = None
    priority: int | None = Field(default=None, ge=0, le=4)
    estimated_minutes: int | None = Field(default=None, ge=0)
    content: str | None = None
    content_refs: list[str] | None = None


class Task(TaskBase):
    """Complete task entity returned from database (template layer only)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    parent_id: str | None = None
    project_id: str

    # Versioning
    version: int = 1
    version_tag: str | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime


class TaskDetail(Task):
    """Extended task with related data for detailed views."""

    # Computed relationships
    learning_objectives: list["LearningObjective"] = Field(default_factory=list)  # type: ignore
    children: list["Task"] = Field(default_factory=list)
    comments: list["Comment"] = Field(default_factory=list)  # type: ignore

    # Dependency info
    blocked_by: list["TaskSummary"] = Field(default_factory=list)
    blocks: list["TaskSummary"] = Field(default_factory=list)


class TaskSummary(BaseModel):
    """Minimal task info for lists and references."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    task_type: TaskType
    priority: int


# ============================================================================
# SQLAlchemy Models (for database)
# ============================================================================


class TaskModel(Base, TimestampMixin):
    """
    SQLAlchemy model for tasks table.

    Template layer entity - no status, closed_at, or close_reason.
    Those fields are in LearnerTaskProgressModel.
    """

    __tablename__ = "tasks"

    # Primary key with hierarchical ID
    id: Mapped[str] = mapped_column(String, primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Core fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    acceptance_criteria: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    # Type and priority
    task_type: Mapped[str] = mapped_column(String, default="task")
    priority: Mapped[int] = mapped_column(Integer, default=2)

    # Estimation
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Learning content
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_refs: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)
    version_tag: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    parent: Mapped[Optional["TaskModel"]] = relationship(
        "TaskModel", remote_side=[id], backref="children", foreign_keys=[parent_id]
    )

    learning_objectives: Mapped[list["LearningObjectiveModel"]] = relationship(  # type: ignore
        "LearningObjectiveModel",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    acceptance_criteria_list: Mapped[list["AcceptanceCriterionModel"]] = relationship(  # type: ignore
        "AcceptanceCriterionModel",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    status_summaries: Mapped[list["StatusSummaryModel"]] = relationship(  # type: ignore
        "StatusSummaryModel",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    comments: Mapped[list["CommentModel"]] = relationship(  # type: ignore
        "CommentModel",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    submissions: Mapped[list["SubmissionModel"]] = relationship(  # type: ignore
        "SubmissionModel",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    learner_progress: Mapped[list["LearnerTaskProgressModel"]] = relationship(  # type: ignore
        "LearnerTaskProgressModel",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    # Dependencies (via association)
    dependencies: Mapped[list["DependencyModel"]] = relationship(  # type: ignore
        "DependencyModel",
        foreign_keys="DependencyModel.task_id",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    dependents: Mapped[list["DependencyModel"]] = relationship(  # type: ignore
        "DependencyModel",
        foreign_keys="DependencyModel.depends_on_id",
        back_populates="depends_on",
        cascade="all, delete-orphan",
    )
