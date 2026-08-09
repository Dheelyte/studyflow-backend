"""partial index for the scheduled expiry sweep

The sweep scans for paid users whose period has ended. A partial index keeps
that proportional to the number of expiring subscribers rather than the whole
users table, and stays tiny because it only covers paid rows.

Revision ID: e5a2c9d7f148
Revises: d4f1b8c6e037
Create Date: 2026-08-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5a2c9d7f148'
down_revision: Union[str, None] = 'd4f1b8c6e037'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = 'ix_users_paid_plan_expiry'


def upgrade() -> None:
    # Partial indexes are Postgres-specific; the test suite runs on SQLite via
    # create_all and never sees this migration.
    if op.get_bind().dialect.name == 'postgresql':
        op.create_index(
            INDEX_NAME,
            'users',
            ['plan_expires_at'],
            postgresql_where=sa.text("plan <> 'free'"),
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        op.drop_index(INDEX_NAME, table_name='users')
