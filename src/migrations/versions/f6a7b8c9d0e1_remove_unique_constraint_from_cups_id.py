"""Remove unique constraint from printjob cups_id

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-11 13:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the unique constraint on printjob.cups_id.

    CUPS restarts its job-ID counter after a service reset, so the same
    cups_id can legitimately appear more than once across different CUPS
    lifetimes.  The field is still used for status-polling by DB job UUID,
    so uniqueness is not required for correctness.
    """
    op.drop_constraint('printjob_cups_id_key', 'printjob', type_='unique')


def downgrade() -> None:
    """Re-add the unique constraint on printjob.cups_id."""
    op.create_unique_constraint('printjob_cups_id_key', 'printjob', ['cups_id'])
