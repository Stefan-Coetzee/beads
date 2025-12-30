"""
Validation models for the Learning Task Tracker.

Pass/fail result for a submission.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class ValidatorType(str, Enum):
    """Type of validator that checked the submission."""

    AUTOMATED = "automated"  # System/test runner
    MANUAL = "manual"  # Human reviewer


# ============================================================================
# Pydantic Models (for API/validation)
# ============================================================================


class ValidationBase(BaseModel):
    """Base validation fields."""

    passed: bool
    error_message: str | None = Field(
        default=None, description="Error details if validation failed"
    )
    validator_type: ValidatorType = Field(default=ValidatorType.AUTOMATED)


class ValidationCreate(ValidationBase):
    """Schema for creating a validation."""

    submission_id: str
    task_id: str


class Validation(ValidationBase):
    """Complete validation entity."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    submission_id: str
    task_id: str
    validated_at: datetime


# ============================================================================
# SQLAlchemy Models (for database)
# ============================================================================


class ValidationModel(Base):
    """SQLAlchemy model for validations table."""

    __tablename__ = "validations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    submission_id: Mapped[str] = mapped_column(
        String, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )

    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    validator_type: Mapped[str] = mapped_column(String, default="automated")

    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    submission: Mapped["SubmissionModel"] = relationship(  # type: ignore
        "SubmissionModel", back_populates="validations"
    )
