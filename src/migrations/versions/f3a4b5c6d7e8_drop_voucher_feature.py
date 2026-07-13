"""Drop the voucher feature entirely (table, indexes, enum type)

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-07-13 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Voucher functionality has been retired; remove the table and its
    dedicated enum type. No-op on databases where the table was already
    absent (e.g. it's created IF EXISTS-guarded)."""
    op.execute("DROP TABLE IF EXISTS voucher")
    op.execute("DROP TYPE IF EXISTS voucherstatus")


def downgrade() -> None:
    """Recreate the voucher table as it was (empty — data is not restored)."""
    op.create_table(
        'voucher',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('code', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'REDEEMED', 'EXPIRED', 'CANCELLED', name='voucherstatus'), nullable=False),
        sa.Column('created_by_id', sa.Uuid(), nullable=True),
        sa.Column('created_by_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('redeemed_by_id', sa.Uuid(), nullable=True),
        sa.Column('redeemed_by_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('redeemed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['redeemed_by_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_voucher_code'), 'voucher', ['code'], unique=True)
    op.create_index(op.f('ix_voucher_id'), 'voucher', ['id'], unique=False)
    op.create_index(op.f('ix_voucher_created_by_id'), 'voucher', ['created_by_id'], unique=False)
    op.create_index(op.f('ix_voucher_redeemed_by_id'), 'voucher', ['redeemed_by_id'], unique=False)
