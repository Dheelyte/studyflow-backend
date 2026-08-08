"""add billing: user plan, subscriptions, usage counters, payment transactions

Adds the freemium tier column on users (everyone starts on 'free') plus the
Paystack bookkeeping tables and the generic per-period usage counter that
generalizes screen_tutor_usage.

Revision ID: c3e0a7b5d926
Revises: b2d9f6a4c815
Create Date: 2026-08-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3e0a7b5d926'
down_revision: Union[str, None] = 'b2d9f6a4c815'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('plan', sa.String(length=20), nullable=False, server_default='free'),
    )

    op.create_table(
        'subscriptions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('tier', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('interval', sa.String(length=20), nullable=False),
        sa.Column('paystack_plan_code', sa.String(length=64), nullable=False),
        sa.Column('paystack_customer_code', sa.String(length=64), nullable=True),
        sa.Column('paystack_subscription_code', sa.String(length=64), nullable=True),
        sa.Column('paystack_email_token', sa.String(length=64), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('paystack_subscription_code'),
    )
    op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'])

    op.create_table(
        'usage_counters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('metric', sa.String(length=50), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'metric', 'period_start', name='unique_user_metric_period'),
    )
    op.create_index('ix_usage_counters_id', 'usage_counters', ['id'])
    op.create_index('ix_usage_counters_user_id', 'usage_counters', ['user_id'])

    op.create_table(
        'payment_transactions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('reference', sa.String(length=128), nullable=False),
        sa.Column('amount_kobo', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='NGN'),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('raw_event', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference'),
    )
    op.create_index('ix_payment_transactions_user_id', 'payment_transactions', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_payment_transactions_user_id', table_name='payment_transactions')
    op.drop_table('payment_transactions')
    op.drop_index('ix_usage_counters_user_id', table_name='usage_counters')
    op.drop_index('ix_usage_counters_id', table_name='usage_counters')
    op.drop_table('usage_counters')
    op.drop_index('ix_subscriptions_user_id', table_name='subscriptions')
    op.drop_table('subscriptions')
    op.drop_column('users', 'plan')
