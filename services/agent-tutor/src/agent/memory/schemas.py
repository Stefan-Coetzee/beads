"""Pydantic models for learner memory."""

from pydantic import BaseModel, Field


class LearnerProfile(BaseModel):
    """Structured learner profile — persists across all projects."""

    name: str | None = None
    programming_experience: str | None = None
    learning_style: str | None = None
    communication_preferences: str | None = None
    strengths: list[str] = Field(default_factory=list)
    areas_for_growth: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    background: str | None = None


class MemoryEntry(BaseModel):
    """A single observation about a learner."""

    text: str
    context: str | None = None
    source: str = "agent"
