"""Expense paid_by_admin_id: who fronted the money, distinct from who recorded it

Revision ID: cfd4f907f806
Revises: ee26aa75d167
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cfd4f907f806'
down_revision: Union[str, Sequence[str], None] = 'ee26aa75d167'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('expense', sa.Column('paid_by_admin_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_expense_paid_by_admin_id'), 'expense', ['paid_by_admin_id'], unique=False)
    op.create_foreign_key(
        'fk_expense_paid_by_admin_id_user', 'expense', 'user', ['paid_by_admin_id'], ['id'], ondelete='SET NULL'
    )
    # Backfill existing rows: before this column existed, the recorder was
    # always assumed to be the payer — the Transaction.actor_id already
    # reflects that historically, so this keeps Expense.paid_by_admin_id
    # consistent with it for any code that reads the Expense row directly.
    op.execute('UPDATE expense SET paid_by_admin_id = recorded_by_admin_id WHERE paid_by_admin_id IS NULL')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_expense_paid_by_admin_id_user', 'expense', type_='foreignkey')
    op.drop_index(op.f('ix_expense_paid_by_admin_id'), table_name='expense')
    op.drop_column('expense', 'paid_by_admin_id')
