"""backfill_two_sided_true

Revision ID: 1593fc514457
Revises: fb56e562724a
Create Date: 2026-03-07 18:14:11.243539

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '1593fc514457'
down_revision: Union[str, Sequence[str], None] = 'fb56e562724a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill: all pre-existing print jobs assumed to have been two-sided."""
    op.execute("UPDATE printjob SET two_sided = TRUE WHERE two_sided = FALSE")


def downgrade() -> None:
    """No rollback — we cannot know which original jobs were one-sided."""
    pass
