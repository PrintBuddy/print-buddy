"""InventoryMovement notes: free-text detail for manual stock adjustments

Revision ID: 19f57d1d4148
Revises: f4c6a5a35027
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '19f57d1d4148'
down_revision: Union[str, Sequence[str], None] = 'f4c6a5a35027'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'inventorymovement',
        sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('inventorymovement', 'notes')
