"""
Comment models for the Learning Task Tracker.

Feedback and discussion on tasks.
Comments can be shared (visible to all learners) or private to a specific learner.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base

# ============================================================================
# Pydantic Models (for API/validation)
# ============================================================================


class CommentBase(BaseModel):
    """Base comment fields."""

    text: str = Field(..., min_length=1)
    author: str = Field(..., description="Author ID: learner_id, 'system', or 'tutor'")
    learner_id: str | None = Field(
        default=None,
        description="If set, comment is private to this learner. If NULL, comment is shared/visible to all.",
    )


class CommentCreate(CommentBase):
    """Schema for creating a comment."""

    task_id: str


class Comment(CommentBase):
    """Complete comment entity."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    created_at: datetime


# ============================================================================
# SQLAlchemy Models (for database)
# ============================================================================


class CommentModel(Base):
    """SQLAlchemy model for comments table."""

    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learner_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("learners.id", ondelete="CASCADE"), nullable=True
    )

    author: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    task: Mapped["TaskModel"] = relationship(  # type: ignore
        "TaskModel", back_populates="comments"
    )
    learner: Mapped[Optional["LearnerModel"]] = relationship(  # type: ignore
        "LearnerModel", back_populates="comments"
    )

    # Index for efficient learner-scoped queries
    __table_args__ = (Index("idx_comments_task_learner", "task_id", "learner_id"),)
