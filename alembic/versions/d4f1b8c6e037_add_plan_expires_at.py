"""add users.plan_expires_at for lazy subscription expiry checks

Denormalises subscriptions.current_period_end onto the user so the per-request
expiry check costs no extra query. Backfilled from any subscription that still
confers a paid tier.

Revision ID: d4f1b8c6e037
Revises: c3e0a7b5d926
Create Date: 2026-08-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4f1b8c6e037'
down_revision: Union[str, None] = 'c3e0a7b5d926'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('plan_expires_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Seed from existing subscriptions so already-paying users aren't seen as
    # expired the moment this ships. UPDATE...FROM is Postgres syntax; skip it
    # on SQLite, which is only used by the test suite (created via create_all).
    if op.get_bind().dialect.name == 'postgresql':
        op.execute(
            """
            UPDATE users
               SET plan_expires_at = s.current_period_end
              FROM subscriptions s
             WHERE s.user_id = users.id
               AND s.status IN ('active', 'non_renewing', 'past_due')
               AND s.current_period_end IS NOT NULL
            """
        )


def downgrade() -> None:
    op.drop_column('users', 'plan_expires_at')
