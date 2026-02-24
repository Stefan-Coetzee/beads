"""add_conversation_threads

Revision ID: b4e8c2a13f91
Revises: 87a33b9dfbb7
Create Date: 2026-02-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4e8c2a13f91'
down_revision: Union[str, Sequence[str], None] = '87a33b9dfbb7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('conversation_threads',
    sa.Column('thread_id', sa.String(), nullable=False),
    sa.Column('learner_id', sa.String(), nullable=False),
    sa.Column('project_id', sa.String(), nullable=False),
    sa.Column('active_task_id', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['learner_id'], ['learners.id'], name=op.f('fk_conversation_threads_learner_id_learners')),
    sa.PrimaryKeyConstraint('thread_id', name=op.f('pk_conversation_threads'))
    )
    op.create_index('idx_thread_learner', 'conversation_threads', ['learner_id'], unique=False)
    op.create_index('idx_thread_project_learner', 'conversation_threads', ['project_id', 'learner_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_thread_project_learner', table_name='conversation_threads')
    op.drop_index('idx_thread_learner', table_name='conversation_threads')
    op.drop_table('conversation_threads')
