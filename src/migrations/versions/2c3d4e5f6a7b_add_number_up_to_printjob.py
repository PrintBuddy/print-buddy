"""add_number_up_to_printjob

Revision ID: 2c3d4e5f6a7b
Revises: fb56e562724a
Create Date: 2026-05-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '2c3d4e5f6a7b'
down_revision: Union[str, Sequence[str], None] = 'fb56e562724a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add number_up field to track pages per sheet."""
    op.add_column('printjob', sa.Column('number_up', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('printjob', 'number_up')
