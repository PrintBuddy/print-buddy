"""Product purchases: spiral binding as a standalone purchasable item

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-07-19 00:00:04.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e8f9a0b1c2d3'
down_revision: Union[str, Sequence[str], None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SPIRAL_BINDING_ID = str(uuid.uuid4())


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'product',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('inventory_item_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventoryitem.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'PRODUCT_PURCHASE'")

    op.add_column('transaction', sa.Column('related_product_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_transaction_related_product_id_product',
        'transaction', 'product',
        ['related_product_id'], ['id'], ondelete='SET NULL'
    )

    op.add_column('inventorymovement', sa.Column('related_product_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_inventorymovement_related_product_id_product',
        'inventorymovement', 'product',
        ['related_product_id'], ['id'], ondelete='SET NULL'
    )

    # Seed the actual motivating case — the €1 spiral binding the
    # residence already sells in person. inventory_item_id stays null
    # until an admin sets up a "Binding Supply" InventoryItem and links it
    # via PATCH; the purchase route already handles that being unset.
    op.execute(f"""
        INSERT INTO product (id, name, price, is_active, created_at, updated_at)
        VALUES ('{SPIRAL_BINDING_ID}', 'Spiral Binding', 1.00, true, now(), now())
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_inventorymovement_related_product_id_product', 'inventorymovement', type_='foreignkey')
    op.drop_column('inventorymovement', 'related_product_id')

    op.drop_constraint('fk_transaction_related_product_id_product', 'transaction', type_='foreignkey')
    op.drop_column('transaction', 'related_product_id')

    op.drop_table('product')
