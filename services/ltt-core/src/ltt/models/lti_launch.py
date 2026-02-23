"""
LTI active launch record — persists grade passback context.

Stores the launch_id and AGS (grade passback) parameters per
learner+project so grades can be sent even after Redis expires.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class LTILaunch(Base):
    """Persists the active LTI launch context needed for grade passback."""

    __tablename__ = "lti_launches"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # launch_id
    learner_id: Mapped[str] = mapped_column(
        String, ForeignKey("learners.id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    lti_sub: Mapped[str] = mapped_column(String, nullable=False)
    ags_lineitems: Mapped[str | None] = mapped_column(Text, nullable=True)
    ags_scope: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_lti_launch_learner_project", "learner_id", "project_id"),
    )
