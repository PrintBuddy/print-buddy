"""Inventory item is_active: soft-deactivate instead of hard delete

Revision ID: ee26aa75d167
Revises: 69aca57537d2
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee26aa75d167'
down_revision: Union[str, Sequence[str], None] = '69aca57537d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('inventoryitem', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('inventoryitem', 'is_active')
