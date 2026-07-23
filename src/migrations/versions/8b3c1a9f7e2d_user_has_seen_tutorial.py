"""User has_seen_tutorial: track first-time onboarding tutorial

Revision ID: 8b3c1a9f7e2d
Revises: 19f57d1d4148
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b3c1a9f7e2d'
down_revision: Union[str, Sequence[str], None] = '19f57d1d4148'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('user', sa.Column('has_seen_tutorial', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user', 'has_seen_tutorial')
