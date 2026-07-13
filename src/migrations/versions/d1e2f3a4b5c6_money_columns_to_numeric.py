"""Convert money columns from float8 to numeric(10,2)

Revision ID: d1e2f3a4b5c6
Revises: 2c3d4e5f6a7b
Create Date: 2026-07-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = '2c3d4e5f6a7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NUMERIC_COLUMNS = [
    ('user', 'balance'),
    ('user', 'credit_limit'),
    ('transaction', 'amount'),
    ('transaction', 'balance_after'),
    ('printjob', 'cost'),
    ('printer', 'price_per_page_bw'),
    ('printer', 'price_per_page_color'),
]


def upgrade() -> None:
    """Store money as exact fixed-point NUMERIC(10,2) instead of float8,
    which was accumulating sub-cent binary-float drift on repeated
    arithmetic (e.g. balance = balance + delta)."""
    for table, column in NUMERIC_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.Float(),
            type_=sa.Numeric(10, 2),
            postgresql_using=f"{column}::numeric(10,2)",
        )


def downgrade() -> None:
    """Revert to float8."""
    for table, column in NUMERIC_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.Numeric(10, 2),
            type_=sa.Float(),
            postgresql_using=f"{column}::double precision",
        )
