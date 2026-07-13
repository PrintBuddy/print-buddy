"""Add missing indexes on FK columns

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-07-13 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column) pairs that are FKs with no index today. Note:
# refundrequest.user_id / .print_job_id already have indexes from the
# original a3f7c1d2e5b8_added_refund_request migration and are deliberately
# not repeated here. voucher's FKs are dropped along with the whole table
# in the next migration instead of being indexed.
INDEXED_FK_COLUMNS = [
    ('transaction', 'user_id'),
    ('printjob', 'user_id'),
    ('printjob', 'printer_id'),
    ('printjob', 'file_id'),
]


def upgrade() -> None:
    for table, column in INDEXED_FK_COLUMNS:
        op.create_index(
            op.f(f'ix_{table}_{column}'), table, [column], unique=False
        )


def downgrade() -> None:
    for table, column in INDEXED_FK_COLUMNS:
        op.drop_index(op.f(f'ix_{table}_{column}'), table_name=table)
