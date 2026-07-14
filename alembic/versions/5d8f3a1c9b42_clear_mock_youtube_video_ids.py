"""clear mock youtube video ids

Revision ID: 5d8f3a1c9b42
Revises: 4c92ad0f7b21
Create Date: 2026-05-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5d8f3a1c9b42'
down_revision: Union[str, None] = '4c92ad0f7b21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MOCK_VIDEO_IDS = (
    'dQw4w9WgXcQ',
    'rfscVS0vtbw',
    'ZyhVh-qy4gg',
    'HXV3zeQKqGY',
    'b9eMGE7QtTk',
)


def upgrade() -> None:
    stmt = sa.text(
        "UPDATE topics SET youtube_video_id = NULL "
        "WHERE youtube_video_id IN :ids"
    ).bindparams(sa.bindparam("ids", expanding=True))
    op.get_bind().execute(stmt, {"ids": list(MOCK_VIDEO_IDS)})


def downgrade() -> None:
    pass
