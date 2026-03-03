"""Fix transaction user_id FK to use ON DELETE CASCADE

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-03-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop existing FK and recreate with ON DELETE CASCADE."""
    op.drop_constraint('transaction_user_id_fkey', 'transaction', type_='foreignkey')
    op.create_foreign_key(
        'transaction_user_id_fkey',
        'transaction', 'user',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    """Revert FK to no cascade behavior."""
    op.drop_constraint('transaction_user_id_fkey', 'transaction', type_='foreignkey')
    op.create_foreign_key(
        'transaction_user_id_fkey',
        'transaction', 'user',
        ['user_id'], ['id']
    )
