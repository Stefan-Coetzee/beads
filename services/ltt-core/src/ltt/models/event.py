"""
Event models for the Learning Task Tracker.

Record of all changes for debugging and history (audit trail).
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class EventType(StrEnum):
    """Types of audit events."""

    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    CLOSED = "closed"
    REOPENED = "reopened"
    DEPENDENCY_ADDED = "dependency_added"
    DEPENDENCY_REMOVED = "dependency_removed"
    COMMENT_ADDED = "comment_added"
    SUBMISSION_CREATED = "submission_created"
    VALIDATION_COMPLETED = "validation_completed"
    OBJECTIVE_ACHIEVED = "objective_achieved"


# ============================================================================
# Pydantic Models (for API/validation)
# ============================================================================


class EventBase(BaseModel):
    """Base event fields."""

    entity_type: str = Field(..., description="Type of entity: task, submission, etc.")
    entity_id: str
    event_type: EventType
    actor: str = Field(..., description="Who triggered the event")
    old_value: str | None = None
    new_value: str | None = None


class EventCreate(EventBase):
    """Schema for creating an event."""

    pass


class Event(EventBase):
    """Complete event entity."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


# ============================================================================
# SQLAlchemy Models (for database)
# ============================================================================


class EventModel(Base):
    """SQLAlchemy model for events table."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Composite index for efficient entity lookups
    __table_args__ = (Index("idx_events_entity", "entity_type", "entity_id"),)
