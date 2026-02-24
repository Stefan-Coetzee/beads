"""
Conversation thread tracking — correlates LangGraph thread IDs
with learners and projects.

The actual conversation state lives in the checkpoint database
(managed by LangGraph's PostgresSaver).  This table provides the
mapping layer so we can answer questions like:

- "Show all conversations for learner X"
- "Which learners have chatted about project Y?"
- "What task was the learner working on in thread Z?"
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class ConversationThread(Base):
    """Maps a LangGraph thread_id to a learner, project, and (optionally) task."""

    __tablename__ = "conversation_threads"

    thread_id: Mapped[str] = mapped_column(String, primary_key=True)
    learner_id: Mapped[str] = mapped_column(
        String, ForeignKey("learners.id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    active_task_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_thread_learner", "learner_id"),
        Index("idx_thread_project_learner", "project_id", "learner_id"),
    )
