"""add milestone projects

Revision ID: a1f8e4b7c93d
Revises: 9c5e7d3a1b26
Create Date: 2026-07-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1f8e4b7c93d'
down_revision: Union[str, None] = '9c5e7d3a1b26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('playlist_id', sa.Integer(), nullable=False),
        sa.Column('module_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('summary', sa.String(), nullable=False),
        sa.Column('brief', sa.String(), nullable=False),
        sa.Column('estimated_time', sa.String(), nullable=False, server_default=''),
        sa.Column('requirements', sa.JSON(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['playlist_id'], ['playlists.id']),
        sa.ForeignKeyConstraint(['module_id'], ['modules.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'playlist_id', 'module_id', name='unique_playlist_module_project'
        ),
    )
    op.create_index('ix_projects_id', 'projects', ['id'])
    op.create_index('ix_projects_playlist_id', 'projects', ['playlist_id'])
    op.create_index('ix_projects_module_id', 'projects', ['module_id'])
    # The unique constraint above does not cover the capstone: Postgres treats NULLs as
    # distinct, so without this a course could accumulate several capstones.
    op.create_index(
        'uq_projects_capstone_per_playlist',
        'projects',
        ['playlist_id'],
        unique=True,
        postgresql_where=sa.text('module_id IS NULL'),
        sqlite_where=sa.text('module_id IS NULL'),
    )

    op.create_table(
        'user_project_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('completed_requirement_ids', sa.JSON(), nullable=False),
        sa.Column('submission_url', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column(
            'is_completed', sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_id', 'project_id', name='unique_user_project_progress'
        ),
    )
    op.create_index('ix_user_project_progress_id', 'user_project_progress', ['id'])
    op.create_index(
        'ix_user_project_progress_user_id', 'user_project_progress', ['user_id']
    )
    op.create_index(
        'ix_user_project_progress_project_id', 'user_project_progress', ['project_id']
    )


def downgrade() -> None:
    op.drop_index(
        'ix_user_project_progress_project_id', table_name='user_project_progress'
    )
    op.drop_index('ix_user_project_progress_user_id', table_name='user_project_progress')
    op.drop_index('ix_user_project_progress_id', table_name='user_project_progress')
    op.drop_table('user_project_progress')

    op.drop_index('uq_projects_capstone_per_playlist', table_name='projects')
    op.drop_index('ix_projects_module_id', table_name='projects')
    op.drop_index('ix_projects_playlist_id', table_name='projects')
    op.drop_index('ix_projects_id', table_name='projects')
    op.drop_table('projects')
