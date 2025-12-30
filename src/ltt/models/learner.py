"""
Learner models for the Learning Task Tracker.

User profile for tracking progress.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base

# ============================================================================
# Pydantic Models (for API/validation)
# ============================================================================


class LearnerBase(BaseModel):
    """Base learner fields."""

    metadata: dict = Field(default_factory=dict, description="Arbitrary user metadata")


class LearnerCreate(LearnerBase):
    """Schema for creating a learner."""

    id: str | None = Field(default=None, description="External ID if provided")


class Learner(LearnerBase):
    """Complete learner entity."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime


class LearnerProgress(BaseModel):
    """Learner's progress in a project."""

    learner_id: str
    project_id: str

    # Progress stats
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    blocked_tasks: int

    # Computed
    completion_percentage: float

    # Objectives
    objectives_achieved: int
    total_objectives: int

    # Time
    total_time_spent_minutes: int | None = None


# ============================================================================
# SQLAlchemy Models (for database)
# ============================================================================


class LearnerModel(Base):
    """SQLAlchemy model for learners table."""

    __tablename__ = "learners"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    learner_metadata: Mapped[str] = mapped_column(Text, default="{}")  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    submissions: Mapped[list["SubmissionModel"]] = relationship(  # type: ignore
        "SubmissionModel", back_populates="learner"
    )
    status_summaries: Mapped[list["StatusSummaryModel"]] = relationship(  # type: ignore
        "StatusSummaryModel", back_populates="learner"
    )
    task_progress: Mapped[list["LearnerTaskProgressModel"]] = relationship(  # type: ignore
        "LearnerTaskProgressModel",
        back_populates="learner",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["CommentModel"]] = relationship(  # type: ignore
        "CommentModel", back_populates="learner"
    )
