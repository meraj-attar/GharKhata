"""Initial owner and transactions tables.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('email', sa.String(254), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('session_version', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('email'),
    )
    op.create_table(
        'transactions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(7), nullable=False),
        sa.Column('amount', sa.Numeric(11, 2), nullable=False),
        sa.Column('category', sa.String(20), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("type IN ('income', 'expense')", name='valid_type'),
        sa.CheckConstraint('amount > 0 AND amount <= 999999999.99', name='valid_amount'),
        sa.CheckConstraint("(type = 'income' AND category = 'Income') OR (type = 'expense' AND category IN ('Grocery', 'Bills', 'Education', 'Medical', 'EMI / Debt', 'Personal'))", name='valid_category'),
    )
    op.create_index('ix_transactions_user_date', 'transactions', ['user_id', 'date'])


def downgrade():
    op.drop_index('ix_transactions_user_date', table_name='transactions')
    op.drop_table('transactions')
    op.drop_table('users')
