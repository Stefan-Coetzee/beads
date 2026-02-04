"""
Submission models for the Learning Task Tracker.

Learner's proof of work for a task.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class SubmissionType(str, Enum):
    """Type of submission content."""

    CODE = "code"
    SQL = "sql"
    JUPYTER_CELL = "jupyter_cell"
    TEXT = "text"
    RESULT_SET = "result_set"


# ============================================================================
# Pydantic Models (for API/validation)
# ============================================================================


class SubmissionBase(BaseModel):
    """Base submission fields."""

    submission_type: SubmissionType
    content: str = Field(..., min_length=1)


class SubmissionCreate(SubmissionBase):
    """Schema for creating a submission."""

    task_id: str
    learner_id: str


class Submission(SubmissionBase):
    """Complete submission entity."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    learner_id: str

    attempt_number: int = 1
    submitted_at: datetime


class SubmissionWithValidation(Submission):
    """Submission with its validation result."""

    validation: Optional["Validation"] = None  # type: ignore


# ============================================================================
# SQLAlchemy Models (for database)
# ============================================================================


class SubmissionModel(Base):
    """SQLAlchemy model for submissions table."""

    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    learner_id: Mapped[str] = mapped_column(
        String, ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )

    submission_type: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    task: Mapped["TaskModel"] = relationship(  # type: ignore
        "TaskModel", back_populates="submissions"
    )
    learner: Mapped["LearnerModel"] = relationship(  # type: ignore
        "LearnerModel", back_populates="submissions"
    )
    validations: Mapped[list["ValidationModel"]] = relationship(  # type: ignore
        "ValidationModel",
        back_populates="submission",
        cascade="all, delete-orphan",
    )

    # Composite index for efficient lookups
    __table_args__ = (Index("idx_submissions_task_learner", "task_id", "learner_id"),)
