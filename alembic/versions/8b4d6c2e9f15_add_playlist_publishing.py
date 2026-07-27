"""add playlist publishing fields

Revision ID: 8b4d6c2e9f15
Revises: 7a3c5b9d2e84
Create Date: 2026-07-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8b4d6c2e9f15'
down_revision: Union[str, None] = '7a3c5b9d2e84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default keeps existing rows valid; every pre-existing playlist stays private.
    op.add_column(
        'playlists',
        sa.Column(
            'is_public', sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.add_column(
        'playlists',
        sa.Column(
            'is_featured', sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.add_column('playlists', sa.Column('slug', sa.String(length=255), nullable=True))
    op.add_column(
        'playlists',
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_playlists_is_public', 'playlists', ['is_public'])
    op.create_index('ix_playlists_slug', 'playlists', ['slug'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_playlists_slug', table_name='playlists')
    op.drop_index('ix_playlists_is_public', table_name='playlists')
    op.drop_column('playlists', 'published_at')
    op.drop_column('playlists', 'slug')
    op.drop_column('playlists', 'is_featured')
    op.drop_column('playlists', 'is_public')
