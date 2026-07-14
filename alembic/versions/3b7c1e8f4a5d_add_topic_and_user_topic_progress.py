"""add_topic_and_user_topic_progress

Revision ID: 3b7c1e8f4a5d
Revises: 2a93a4d790a3
Create Date: 2026-04-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b7c1e8f4a5d'
down_revision: Union[str, None] = '2a93a4d790a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'topics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('youtube_video_id', sa.String(), nullable=True),
        sa.Column('lesson_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_topics_id'), 'topics', ['id'], unique=False)

    op.create_table(
        'user_topic_progress',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('is_completed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'topic_id', name='unique_user_topic_progress'),
    )
    op.create_index(op.f('ix_user_topic_progress_id'), 'user_topic_progress', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_topic_progress_id'), table_name='user_topic_progress')
    op.drop_table('user_topic_progress')
    op.drop_index(op.f('ix_topics_id'), table_name='topics')
    op.drop_table('topics')
