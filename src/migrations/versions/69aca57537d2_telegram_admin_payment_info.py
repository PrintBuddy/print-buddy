"""Telegram admin payment info: per-admin phone/transfer/bank contact details

Revision ID: 69aca57537d2
Revises: a0b1c2d3e4f5
Create Date: 2026-07-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '69aca57537d2'
down_revision: Union[str, Sequence[str], None] = 'a0b1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('telegramadmin', sa.Column('phone_number', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('telegramadmin', sa.Column('accepts_transfer', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('telegramadmin', sa.Column('bank_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('telegramadmin', sa.Column('bank_iban', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('telegramadmin', sa.Column('bank_link', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('telegramadmin', 'bank_link')
    op.drop_column('telegramadmin', 'bank_iban')
    op.drop_column('telegramadmin', 'bank_name')
    op.drop_column('telegramadmin', 'accepts_transfer')
    op.drop_column('telegramadmin', 'phone_number')
