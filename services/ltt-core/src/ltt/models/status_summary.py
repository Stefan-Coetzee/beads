"""
Status Summary models for the Learning Task Tracker.

Versioned status updates and progress notes per learner per task.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base

# ============================================================================
# Pydantic Models (for API/validation)
# ============================================================================


class StatusSummaryBase(BaseModel):
    """Base status summary fields."""

    summary: str = Field(..., min_length=1)


class StatusSummaryCreate(StatusSummaryBase):
    """Schema for creating a status summary."""

    task_id: str
    learner_id: str


class StatusSummary(StatusSummaryBase):
    """Complete status summary entity."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    learner_id: str
    version: int = 1
    created_at: datetime


# ============================================================================
# SQLAlchemy Models (for database)
# ============================================================================


class StatusSummaryModel(Base):
    """SQLAlchemy model for status_summaries table."""

    __tablename__ = "status_summaries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    learner_id: Mapped[str] = mapped_column(
        String, ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    task: Mapped["TaskModel"] = relationship(  # type: ignore
        "TaskModel", back_populates="status_summaries"
    )
    learner: Mapped["LearnerModel"] = relationship(  # type: ignore
        "LearnerModel", back_populates="status_summaries"
    )

    # Composite index for efficient lookups
    __table_args__ = (Index("idx_status_summaries_task_learner", "task_id", "learner_id"),)
