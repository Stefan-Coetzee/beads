"""
Learning Objective models for the Learning Task Tracker.

Pedagogical goals attached to tasks.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class BloomLevel(StrEnum):
    """Bloom's Taxonomy cognitive levels."""

    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class ObjectiveTaxonomy(StrEnum):
    """Supported learning taxonomies."""

    BLOOM = "bloom"
    CUSTOM = "custom"


# ============================================================================
# Pydantic Models (for API/validation)
# ============================================================================


class LearningObjectiveBase(BaseModel):
    """Base learning objective fields."""

    taxonomy: ObjectiveTaxonomy = Field(default=ObjectiveTaxonomy.BLOOM)
    level: BloomLevel | None = Field(
        default=None, description="Cognitive level (for Bloom's taxonomy)"
    )
    description: str = Field(..., min_length=1)


class LearningObjectiveCreate(LearningObjectiveBase):
    """Schema for creating a learning objective."""

    task_id: str


class LearningObjective(LearningObjectiveBase):
    """Complete learning objective entity."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    created_at: datetime


# ============================================================================
# SQLAlchemy Models (for database)
# ============================================================================


class LearningObjectiveModel(Base):
    """SQLAlchemy model for learning_objectives table."""

    __tablename__ = "learning_objectives"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    taxonomy: Mapped[str] = mapped_column(String, default="bloom")
    level: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    task: Mapped["TaskModel"] = relationship(  # type: ignore
        "TaskModel", back_populates="learning_objectives"
    )
