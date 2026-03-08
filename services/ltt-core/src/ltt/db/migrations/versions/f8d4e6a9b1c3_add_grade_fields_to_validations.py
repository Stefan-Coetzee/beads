"""add grade, grader_type, feedback to validations

Revision ID: f8d4e6a9b1c3
Revises: e7f3a1b2c4d5
Create Date: 2026-03-06 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8d4e6a9b1c3"
down_revision: str | None = "e7f3a1b2c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("validations", sa.Column("grade", sa.Float(), nullable=True))
    op.add_column(
        "validations",
        sa.Column("grader_type", sa.String(20), server_default="auto"),
    )
    op.add_column("validations", sa.Column("feedback", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("validations", "feedback")
    op.drop_column("validations", "grader_type")
    op.drop_column("validations", "grade")
