"""
LearnerTaskProgress models for the Learning Task Tracker.

Per-learner status and progress tracking for tasks.
This is the INSTANCE LAYER that pairs with Task (template layer).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .task import TaskStatus

# ============================================================================
# Pydantic Models (for API/validation)
# ============================================================================


class LearnerTaskProgressBase(BaseModel):
    """Base fields for learner task progress."""

    status: TaskStatus = Field(default=TaskStatus.OPEN)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    close_reason: str | None = Field(default=None)


class LearnerTaskProgressCreate(LearnerTaskProgressBase):
    """Schema for creating learner task progress."""

    task_id: str
    learner_id: str


class LearnerTaskProgress(LearnerTaskProgressBase):
    """Complete learner task progress entity."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    learner_id: str
    created_at: datetime
    updated_at: datetime


# ============================================================================
# SQLAlchemy Models (for database)
# ============================================================================


class LearnerTaskProgressModel(Base, TimestampMixin):
    """
    SQLAlchemy model for learner_task_progress table.

    Instance layer - tracks per-learner status for each task.
    """

    __tablename__ = "learner_task_progress"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    learner_id: Mapped[str] = mapped_column(
        String, ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    task: Mapped["TaskModel"] = relationship(  # type: ignore
        "TaskModel", back_populates="learner_progress"
    )
    learner: Mapped["LearnerModel"] = relationship(  # type: ignore
        "LearnerModel", back_populates="task_progress"
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("task_id", "learner_id", name="uq_task_learner_progress"),
        Index("idx_learner_task_progress_task_learner", "task_id", "learner_id"),
        Index("idx_learner_task_progress_learner_status", "learner_id", "status"),
    )
