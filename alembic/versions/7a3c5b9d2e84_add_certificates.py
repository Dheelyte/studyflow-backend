"""add certificates

Revision ID: 7a3c5b9d2e84
Revises: 6e1f4b2d8c73
Create Date: 2026-05-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7a3c5b9d2e84'
down_revision: Union[str, None] = '6e1f4b2d8c73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'certificates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('playlist_id', sa.Integer(), nullable=False),
        sa.Column('verification_code', sa.String(length=64), nullable=False),
        sa.Column('playlist_title', sa.String(), nullable=False),
        sa.Column('recipient_name', sa.String(), nullable=False),
        sa.Column(
            'issued_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['playlist_id'], ['playlists.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('verification_code'),
        sa.UniqueConstraint(
            'user_id', 'playlist_id', name='unique_user_playlist_certificate'
        ),
    )
    op.create_index('ix_certificates_id', 'certificates', ['id'])
    op.create_index('ix_certificates_user_id', 'certificates', ['user_id'])
    op.create_index('ix_certificates_playlist_id', 'certificates', ['playlist_id'])
    op.create_index(
        'ix_certificates_verification_code', 'certificates', ['verification_code']
    )


def downgrade() -> None:
    op.drop_index('ix_certificates_verification_code', table_name='certificates')
    op.drop_index('ix_certificates_playlist_id', table_name='certificates')
    op.drop_index('ix_certificates_user_id', table_name='certificates')
    op.drop_index('ix_certificates_id', table_name='certificates')
    op.drop_table('certificates')
