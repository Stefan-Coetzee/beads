"""
Acceptance Criterion models for the Learning Task Tracker.

Structured validation rules for tasks.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class CriterionType(StrEnum):
    """Type of acceptance criterion."""

    CODE_TEST = "code_test"  # Automated code test
    SQL_RESULT = "sql_result"  # SQL query result check
    TEXT_MATCH = "text_match"  # Text/pattern matching
    MANUAL = "manual"  # Human review required


# ============================================================================
# Pydantic Models (for API/validation)
# ============================================================================


class AcceptanceCriterionBase(BaseModel):
    """Base acceptance criterion fields."""

    criterion_type: CriterionType
    description: str = Field(..., min_length=1)


class AcceptanceCriterionCreate(AcceptanceCriterionBase):
    """Schema for creating an acceptance criterion."""

    task_id: str


class AcceptanceCriterion(AcceptanceCriterionBase):
    """Complete acceptance criterion entity."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    created_at: datetime


# ============================================================================
# SQLAlchemy Models (for database)
# ============================================================================


class AcceptanceCriterionModel(Base):
    """SQLAlchemy model for acceptance_criteria table."""

    __tablename__ = "acceptance_criteria"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    criterion_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    task: Mapped["TaskModel"] = relationship(  # type: ignore
        "TaskModel", back_populates="acceptance_criteria_list"
    )
