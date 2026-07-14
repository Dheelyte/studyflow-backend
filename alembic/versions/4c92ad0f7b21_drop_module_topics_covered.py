"""drop module topics_covered

Revision ID: 4c92ad0f7b21
Revises: 3b7c1e8f4a5d
Create Date: 2026-05-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4c92ad0f7b21'
down_revision: Union[str, None] = '3b7c1e8f4a5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('modules', 'topics_covered')


def downgrade() -> None:
    op.add_column(
        'modules',
        sa.Column('topics_covered', sa.JSON(), nullable=False, server_default='[]'),
    )
