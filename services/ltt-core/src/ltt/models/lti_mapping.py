"""
LTI user identity mapping model.

Maps LTI sub+iss claims to internal LTT learner IDs.
Supports multiple platforms pointing to the same learner.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class LTIUserMapping(Base):
    """Maps LTI platform user identities to LTT learner records."""

    __tablename__ = "lti_user_mappings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    lti_sub: Mapped[str] = mapped_column(String, nullable=False)
    lti_iss: Mapped[str] = mapped_column(String, nullable=False)
    learner_id: Mapped[str] = mapped_column(String, ForeignKey("learners.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("lti_sub", "lti_iss", name="uq_lti_sub_iss"),
        Index("idx_lti_mapping_sub_iss", "lti_sub", "lti_iss"),
        Index("idx_lti_mapping_learner", "learner_id"),
    )
