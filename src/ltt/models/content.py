"""
Content models for the Learning Task Tracker.

Learning materials that can be attached to tasks.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class ContentType(str, Enum):
    """Type of learning content."""

    MARKDOWN = "markdown"
    CODE = "code"
    VIDEO_REF = "video_ref"
    EXTERNAL_LINK = "external_link"


# ============================================================================
# Pydantic Models (for API/validation)
# ============================================================================


class ContentBase(BaseModel):
    """Base content fields."""

    content_type: ContentType
    body: str
    metadata: dict = {}


class ContentCreate(ContentBase):
    """Schema for creating content."""

    id: str | None = None


class Content(ContentBase):
    """Complete content entity."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime


# ============================================================================
# SQLAlchemy Models (for database)
# ============================================================================


class ContentModel(Base):
    """SQLAlchemy model for content table."""

    __tablename__ = "content"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    content_metadata: Mapped[str] = mapped_column(Text, default="{}")  # JSON string

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
