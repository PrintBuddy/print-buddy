"""Expense logging and inventory management

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-07-19 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, Sequence[str], None] = 'c6d7e8f9a0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Plain inline sa.Enum(...) in a CREATE TABLE column definition — same
    # as every existing enum column in this migration history (e.g.
    # jobstatus/transactiontype in the initial migration). op.create_table
    # already creates the type itself as part of the table's DDL sequence;
    # a separate manual .create() call here (as Phase 0/1 needed for
    # add_column on an *existing* table) would double-create it and fail.
    op.create_table(
        'expense',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('category', sa.Enum('TONER', 'PAPER', 'MAINTENANCE', 'OTHER', name='expensecategory'), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('recorded_by_admin_id', sa.Uuid(), nullable=True),
        sa.Column('receipt_file_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['recorded_by_admin_id'], ['user.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['receipt_file_id'], ['file.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_expense_recorded_by_admin_id'), 'expense', ['recorded_by_admin_id'])

    op.create_table(
        'inventoryitem',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            'category',
            sa.Enum('PAPER', 'TONER_BW', 'TONER_COLOR', 'BINDING_SUPPLY', 'OTHER', name='inventorycategory'),
            nullable=False,
        ),
        sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('current_stock', sa.Numeric(10, 2), nullable=False),
        sa.Column('low_stock_threshold', sa.Numeric(10, 2), nullable=False),
        sa.Column('printer_id', sa.Uuid(), nullable=True),
        sa.Column('reorder_supplier', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['printer_id'], ['printer.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'inventorymovement',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('item_id', sa.Uuid(), nullable=False),
        sa.Column('delta', sa.Numeric(10, 2), nullable=False),
        sa.Column(
            'reason',
            sa.Enum('PURCHASE', 'PRINT_CONSUMPTION', 'MANUAL_ADJUSTMENT', 'PRODUCT_SALE', name='inventorymovementreason'),
            nullable=False,
        ),
        sa.Column('related_job_id', sa.Uuid(), nullable=True),
        sa.Column('related_expense_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['inventoryitem.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['related_job_id'], ['printjob.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['related_expense_id'], ['expense.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_inventorymovement_item_id'), 'inventorymovement', ['item_id'])

    # Append-only, same as transaction/collectionevent — no exempted
    # column here, a movement's own delta/reason never changes after the
    # fact; correcting a mistake means recording a new offsetting movement.
    op.execute("""
        CREATE TRIGGER inventorymovement_append_only
        BEFORE UPDATE OR DELETE ON inventorymovement
        FOR EACH ROW EXECUTE FUNCTION prevent_transaction_mutation();
    """)

    # --- Transaction: EXPENSE type, and the nullability it needs ---
    # New enum labels can't be used in the same transaction they're added
    # in (Postgres restriction, even though ADD VALUE itself is
    # transactional since PG12) — safe here since nothing in this
    # migration inserts an EXPENSE row.
    op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'EXPENSE'")

    op.alter_column('transaction', 'user_id', existing_type=sa.Uuid(), nullable=True)
    op.alter_column('transaction', 'balance_after', existing_type=sa.Numeric(10, 2), nullable=True)

    op.add_column('transaction', sa.Column('related_expense_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_transaction_related_expense_id_expense',
        'transaction', 'expense',
        ['related_expense_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_transaction_related_expense_id_expense', 'transaction', type_='foreignkey')
    op.drop_column('transaction', 'related_expense_id')

    # Enum labels can't be dropped in Postgres without recreating the type
    # entirely — acceptable to leave 'EXPENSE' defined but unused on
    # downgrade rather than rebuild the whole enum + every dependent column.
    op.execute("UPDATE \"transaction\" SET balance_after = 0 WHERE balance_after IS NULL")
    op.alter_column('transaction', 'balance_after', existing_type=sa.Numeric(10, 2), nullable=False)
    op.execute("DELETE FROM \"transaction\" WHERE user_id IS NULL")
    op.alter_column('transaction', 'user_id', existing_type=sa.Uuid(), nullable=False)

    op.execute("DROP TRIGGER IF EXISTS inventorymovement_append_only ON inventorymovement")
    op.drop_index(op.f('ix_inventorymovement_item_id'), table_name='inventorymovement')
    op.drop_table('inventorymovement')
    op.execute("DROP TYPE IF EXISTS inventorymovementreason")

    op.drop_table('inventoryitem')
    op.execute("DROP TYPE IF EXISTS inventorycategory")

    op.drop_index(op.f('ix_expense_recorded_by_admin_id'), table_name='expense')
    op.drop_table('expense')
    op.execute("DROP TYPE IF EXISTS expensecategory")
