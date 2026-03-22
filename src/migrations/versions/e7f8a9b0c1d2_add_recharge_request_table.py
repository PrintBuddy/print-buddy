"""Add recharge request table

Revision ID: e7f8a9b0c1d2
Revises: ce05fe8bddf0
Create Date: 2026-03-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = 'ce05fe8bddf0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'rechargerequest',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('username', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='pending'),
        sa.Column('requester_chat_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('requester_telegram_username', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('requester_first_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('requester_last_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('resolved_by_username', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rechargerequest_id'), 'rechargerequest', ['id'], unique=False)
    op.create_index(op.f('ix_rechargerequest_requester_chat_id'), 'rechargerequest', ['requester_chat_id'], unique=False)
    op.create_index(op.f('ix_rechargerequest_user_id'), 'rechargerequest', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_rechargerequest_user_id'), table_name='rechargerequest')
    op.drop_index(op.f('ix_rechargerequest_requester_chat_id'), table_name='rechargerequest')
    op.drop_index(op.f('ix_rechargerequest_id'), table_name='rechargerequest')
    op.drop_table('rechargerequest')
