"""Admin operational overrides: unsolicited refunds and free reprints

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-07-19 00:00:05.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'f9a0b1c2d3e4'
down_revision: Union[str, Sequence[str], None] = 'e8f9a0b1c2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'FREE_REPRINT'")

    op.add_column('refundrequest', sa.Column('initiated_by_admin_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_refundrequest_initiated_by_admin_id_user',
        'refundrequest', 'user',
        ['initiated_by_admin_id'], ['id'], ondelete='SET NULL'
    )

    op.add_column('printjob', sa.Column('free_reprint_of_job_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_printjob_free_reprint_of_job_id_printjob',
        'printjob', 'printjob',
        ['free_reprint_of_job_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_printjob_free_reprint_of_job_id_printjob', 'printjob', type_='foreignkey')
    op.drop_column('printjob', 'free_reprint_of_job_id')

    op.drop_constraint('fk_refundrequest_initiated_by_admin_id_user', 'refundrequest', type_='foreignkey')
    op.drop_column('refundrequest', 'initiated_by_admin_id')
