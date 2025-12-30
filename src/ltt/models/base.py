"""
Base SQLAlchemy models and common utilities for the Learning Task Tracker.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

# Naming convention for constraints and indexes
# This ensures Alembic generates consistent migration names
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    Provides common metadata and utilities.
    """

    metadata = metadata

    # Type annotation for better IDE support
    __tablename__: str

    def to_dict(self) -> dict[str, Any]:
        """
        Convert model instance to dictionary.

        Useful for debugging and serialization.
        """
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


class TimestampMixin:
    """
    Mixin for models that need created_at and updated_at timestamps.

    Usage:
        class MyModel(Base, TimestampMixin):
            ...
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
