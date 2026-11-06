"""Persist transaction creation idempotency keys per authenticated owner.

Revision ID: 0002_transaction_idempotency
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_transaction_idempotency'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'transaction_idempotency',
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key', sa.String(128), nullable=False),
        sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('transaction_id', sa.Uuid(), sa.ForeignKey('transactions.id', ondelete='CASCADE'), nullable=False),
        sa.PrimaryKeyConstraint('user_id', 'key'),
    )


def downgrade():
    op.drop_table('transaction_idempotency')
