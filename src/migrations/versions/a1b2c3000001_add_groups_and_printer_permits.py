"""Add groups, user-group membership, group-printer permits, and printer.is_restricted

Revision ID: a1b2c3000001
Revises: d4e5f6a7b8c9
Create Date: 2026-03-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'a1b2c3000001'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_restricted column to printer
    op.add_column(
        'printer',
        sa.Column('is_restricted', sa.Boolean(), nullable=False, server_default='false')
    )

    # Create group table
    op.create_table(
        'group',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_group_id'), 'group', ['id'], unique=False)
    op.create_index(op.f('ix_group_name'), 'group', ['name'], unique=True)

    # Create usergroup table
    op.create_table(
        'usergroup',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('group_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'group_id'),
    )

    # Create groupprinterperimit table
    op.create_table(
        'groupprinterperimit',
        sa.Column('group_id', sa.Uuid(), nullable=False),
        sa.Column('printer_id', sa.Uuid(), nullable=False),
        sa.Column('custom_price_bw', sa.Float(), nullable=True),
        sa.Column('custom_price_color', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['group.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['printer_id'], ['printer.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('group_id', 'printer_id'),
    )


def downgrade() -> None:
    op.drop_table('groupprinterperimit')
    op.drop_table('usergroup')
    op.drop_index(op.f('ix_group_name'), table_name='group')
    op.drop_index(op.f('ix_group_id'), table_name='group')
    op.drop_table('group')
    op.drop_column('printer', 'is_restricted')
