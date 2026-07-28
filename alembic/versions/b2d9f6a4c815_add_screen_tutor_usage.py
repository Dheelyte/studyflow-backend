"""add screen tutor daily usage

Tracks only a per-user, per-day question count for the screen tutor quota.
Captured frames are never persisted.

Revision ID: b2d9f6a4c815
Revises: a1f8e4b7c93d
Create Date: 2026-07-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2d9f6a4c815'
down_revision: Union[str, None] = 'a1f8e4b7c93d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'screen_tutor_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('usage_date', sa.Date(), nullable=False),
        sa.Column('question_count', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'usage_date', name='unique_user_screen_tutor_day'),
    )
    op.create_index('ix_screen_tutor_usage_id', 'screen_tutor_usage', ['id'])
    op.create_index('ix_screen_tutor_usage_user_id', 'screen_tutor_usage', ['user_id'])
    op.create_index('ix_screen_tutor_usage_usage_date', 'screen_tutor_usage', ['usage_date'])


def downgrade() -> None:
    op.drop_index('ix_screen_tutor_usage_usage_date', table_name='screen_tutor_usage')
    op.drop_index('ix_screen_tutor_usage_user_id', table_name='screen_tutor_usage')
    op.drop_index('ix_screen_tutor_usage_id', table_name='screen_tutor_usage')
    op.drop_table('screen_tutor_usage')
