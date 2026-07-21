"""Product purchase requests: pending/fulfilled/rejected extras purchases with admin broadcast

Revision ID: a0b1c2d3e4f5
Revises: f9a0b1c2d3e4
Create Date: 2026-07-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a0b1c2d3e4f5'
down_revision: Union[str, Sequence[str], None] = 'f9a0b1c2d3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'productpurchase',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('username', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=True),
        sa.Column('product_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('unit_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('total_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('message', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='pending'),
        sa.Column('admin_message', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('resolved_by_username', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_productpurchase_id'), 'productpurchase', ['id'], unique=False)
    op.create_index(op.f('ix_productpurchase_user_id'), 'productpurchase', ['user_id'], unique=False)

    op.create_table(
        'productpurchasenotification',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('purchase_id', sa.Uuid(), nullable=False),
        sa.Column('chat_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['purchase_id'], ['productpurchase.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_productpurchasenotification_id'), 'productpurchasenotification', ['id'], unique=False)
    op.create_index(
        op.f('ix_productpurchasenotification_purchase_id'), 'productpurchasenotification', ['purchase_id'], unique=False
    )

    op.add_column('transaction', sa.Column('related_product_purchase_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_transaction_related_product_purchase_id_productpurchase',
        'transaction', 'productpurchase',
        ['related_product_purchase_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_transaction_related_product_purchase_id_productpurchase', 'transaction', type_='foreignkey')
    op.drop_column('transaction', 'related_product_purchase_id')

    op.drop_index(op.f('ix_productpurchasenotification_purchase_id'), table_name='productpurchasenotification')
    op.drop_index(op.f('ix_productpurchasenotification_id'), table_name='productpurchasenotification')
    op.drop_table('productpurchasenotification')

    op.drop_index(op.f('ix_productpurchase_user_id'), table_name='productpurchase')
    op.drop_index(op.f('ix_productpurchase_id'), table_name='productpurchase')
    op.drop_table('productpurchase')
