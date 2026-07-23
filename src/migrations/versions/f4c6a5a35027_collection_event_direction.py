"""CollectionEvent direction: track house-pays-admin as well as admin-pays-house

Revision ID: f4c6a5a35027
Revises: cfd4f907f806
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'f4c6a5a35027'
down_revision: Union[str, Sequence[str], None] = 'cfd4f907f806'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'collectionevent',
        sa.Column(
            'direction', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='from_admin'
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('collectionevent', 'direction')
