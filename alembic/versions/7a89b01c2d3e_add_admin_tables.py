"""add admin tables

Revision ID: 7a89b01c2d3e
Revises: 39d76c5ae957
Create Date: 2026-10-01 01:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a89b01c2d3e'
down_revision: Union[str, Sequence[str], None] = '39d76c5ae957'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'admin_users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('admin_id', sa.String(length=100), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('mobile_number', sa.String(length=50), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='ADMIN', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('admin_id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('mobile_number')
    )
    op.create_index(op.f('ix_admin_users_admin_id'), 'admin_users', ['admin_id'], unique=True)
    op.create_index(op.f('ix_admin_users_email'), 'admin_users', ['email'], unique=True)
    op.create_index(op.f('ix_admin_users_id'), 'admin_users', ['id'], unique=False)
    op.create_index(op.f('ix_admin_users_mobile_number'), 'admin_users', ['mobile_number'], unique=True)

    op.create_table(
        'admin_verification_actions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('driver_id', sa.String(length=255), nullable=False),
        sa.Column('admin_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('previous_status', sa.String(length=50), nullable=False),
        sa.Column('new_status', sa.String(length=50), nullable=False),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('rejected_document_type', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['admin_id'], ['admin_users.id'], ),
        sa.ForeignKeyConstraint(['driver_id'], ['drivers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_verification_actions_admin_id'), 'admin_verification_actions', ['admin_id'], unique=False)
    op.create_index(op.f('ix_admin_verification_actions_driver_id'), 'admin_verification_actions', ['driver_id'], unique=False)
    op.create_index(op.f('ix_admin_verification_actions_id'), 'admin_verification_actions', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_admin_verification_actions_id'), table_name='admin_verification_actions')
    op.drop_index(op.f('ix_admin_verification_actions_driver_id'), table_name='admin_verification_actions')
    op.drop_index(op.f('ix_admin_verification_actions_admin_id'), table_name='admin_verification_actions')
    op.drop_table('admin_verification_actions')

    op.drop_index(op.f('ix_admin_users_mobile_number'), table_name='admin_users')
    op.drop_index(op.f('ix_admin_users_id'), table_name='admin_users')
    op.drop_index(op.f('ix_admin_users_email'), table_name='admin_users')
    op.drop_index(op.f('ix_admin_users_admin_id'), table_name='admin_users')
    op.drop_table('admin_users')
