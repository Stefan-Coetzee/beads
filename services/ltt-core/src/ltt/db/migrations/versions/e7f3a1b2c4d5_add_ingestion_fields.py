"""add subtask_type, narrative, tutor_config, max_grade, project_slug to tasks

Revision ID: e7f3a1b2c4d5
Revises: b4e8c2a13f91
Create Date: 2026-03-06 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "e7f3a1b2c4d5"
down_revision: str | None = "b4e8c2a13f91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("subtask_type", sa.String(20), server_default="exercise"))
    op.add_column("tasks", sa.Column("narrative", sa.Boolean(), server_default=sa.text("false")))
    op.add_column("tasks", sa.Column("tutor_config", JSONB(), nullable=True))
    op.add_column("tasks", sa.Column("max_grade", sa.Float(), nullable=True))
    op.add_column("tasks", sa.Column("project_slug", sa.String(64), nullable=True))
    op.create_index(
        "ix_tasks_project_slug_version",
        "tasks",
        ["project_slug", "version"],
        unique=True,
        postgresql_where=sa.text("task_type = 'project'"),
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_project_slug_version", table_name="tasks")
    op.drop_column("tasks", "project_slug")
    op.drop_column("tasks", "max_grade")
    op.drop_column("tasks", "tutor_config")
    op.drop_column("tasks", "narrative")
    op.drop_column("tasks", "subtask_type")
