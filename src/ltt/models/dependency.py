"""
Dependency models for the Learning Task Tracker.

Relationships between tasks that control workflow.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class DependencyType(str, Enum):
    """Type of dependency relationship."""

    BLOCKS = "blocks"  # Task cannot start until dependency closes
    PARENT_CHILD = "parent_child"  # Hierarchical (implicit via parent_id)
    RELATED = "related"  # Informational, no blocking


# ============================================================================
# Pydantic Models (for API/validation)
# ============================================================================


class DependencyBase(BaseModel):
    """Base dependency fields."""

    dependency_type: DependencyType = Field(default=DependencyType.BLOCKS)
    metadata: dict | None = Field(default=None, description="Type-specific metadata")


class DependencyCreate(DependencyBase):
    """Schema for creating a dependency."""

    task_id: str = Field(..., description="The task that depends on another")
    depends_on_id: str = Field(..., description="The task being depended upon")


class Dependency(DependencyBase):
    """Complete dependency entity."""

    model_config = ConfigDict(from_attributes=True)

    task_id: str
    depends_on_id: str
    created_at: datetime
    created_by: str | None = None


class DependencyWithTask(Dependency):
    """Dependency with the related task details."""

    depends_on: "TaskSummary"  # type: ignore


# ============================================================================
# SQLAlchemy Models (for database)
# ============================================================================


class DependencyModel(Base):
    """
    SQLAlchemy model for dependencies table.

    Composite primary key on (task_id, depends_on_id).
    """

    __tablename__ = "dependencies"

    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    depends_on_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )

    dependency_type: Mapped[str] = mapped_column(String, default="blocks")
    dep_metadata: Mapped[str] = mapped_column(Text, default="{}")  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    task: Mapped["TaskModel"] = relationship(  # type: ignore
        "TaskModel", foreign_keys=[task_id], back_populates="dependencies"
    )
    depends_on: Mapped["TaskModel"] = relationship(  # type: ignore
        "TaskModel", foreign_keys=[depends_on_id], back_populates="dependents"
    )
