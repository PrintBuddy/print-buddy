"""Add resolved_by_username to refundrequest

Revision ID: b1c2d3e4f5a6
Revises: a3f7c1d2e5b8
Create Date: 2026-03-02 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a3f7c1d2e5b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add resolved_by_username column to refundrequest table."""
    op.add_column(
        'refundrequest',
        sa.Column('resolved_by_username', sqlmodel.sql.sqltypes.AutoString(), nullable=True)
    )


def downgrade() -> None:
    """Remove resolved_by_username column from refundrequest table."""
    op.drop_column('refundrequest', 'resolved_by_username')
