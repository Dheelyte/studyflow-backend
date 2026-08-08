"""backfill playlist slugs

Course URLs are slug-based, so every playlist needs a slug , not just the
published ones that got a slug from the gallery publish flow.

Revision ID: 9c5e7d3a1b26
Revises: 8b4d6c2e9f15
Create Date: 2026-07-26

"""
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9c5e7d3a1b26'
down_revision: Union[str, None] = '8b4d6c2e9f15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NON_SLUG_CHARS = re.compile(r'[^a-z0-9]+')


def _slugify(value: str) -> str:
    slug = _NON_SLUG_CHARS.sub('-', (value or '').lower()).strip('-')
    return slug[:200].strip('-') or 'course'


def upgrade() -> None:
    conn = op.get_bind()

    rows = conn.execute(
        sa.text("SELECT id, title FROM playlists WHERE slug IS NULL ORDER BY id")
    ).fetchall()

    taken = {
        row[0]
        for row in conn.execute(
            sa.text("SELECT slug FROM playlists WHERE slug IS NOT NULL")
        ).fetchall()
    }

    for playlist_id, title in rows:
        base = _slugify(title)
        slug = base
        # Fall back to the id for uniqueness rather than a random suffix, so the
        # backfill is deterministic and re-runnable.
        if slug in taken:
            slug = f"{base}-{playlist_id}"
        taken.add(slug)

        conn.execute(
            sa.text("UPDATE playlists SET slug = :slug WHERE id = :id"),
            {"slug": slug, "id": playlist_id},
        )


def downgrade() -> None:
    # Slugs are the public identifier now; clearing them on downgrade would break
    # any link already shared, so this is intentionally a no-op.
    pass
