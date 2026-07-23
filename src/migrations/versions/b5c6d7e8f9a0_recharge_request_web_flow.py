"""Recharge request web flow: method, target admin, notification tracking

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-07-19 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b5c6d7e8f9a0'
down_revision: Union[str, Sequence[str], None] = 'a4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Web-created requests have no Telegram chat behind them at all.
    op.alter_column('rechargerequest', 'requester_chat_id', existing_type=sa.VARCHAR(), nullable=True)

    rechargemethod = sa.Enum('CASH', 'TRANSFER', name='rechargemethod')
    rechargemethod.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'rechargerequest',
        sa.Column('method', sa.Enum('CASH', 'TRANSFER', name='rechargemethod', create_type=False), nullable=True),
    )

    op.add_column('rechargerequest', sa.Column('target_telegram_admin_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_rechargerequest_target_telegram_admin_id_telegramadmin',
        'rechargerequest', 'telegramadmin',
        ['target_telegram_admin_id'], ['id'], ondelete='SET NULL'
    )

    op.add_column('rechargerequest', sa.Column('notified_chat_id', sa.String(), nullable=True))
    op.add_column('rechargerequest', sa.Column('notified_message_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('rechargerequest', 'notified_message_id')
    op.drop_column('rechargerequest', 'notified_chat_id')

    op.drop_constraint(
        'fk_rechargerequest_target_telegram_admin_id_telegramadmin', 'rechargerequest', type_='foreignkey'
    )
    op.drop_column('rechargerequest', 'target_telegram_admin_id')

    op.drop_column('rechargerequest', 'method')
    op.execute("DROP TYPE IF EXISTS rechargemethod")

    op.execute('UPDATE rechargerequest SET requester_chat_id = \'\' WHERE requester_chat_id IS NULL')
    op.alter_column('rechargerequest', 'requester_chat_id', existing_type=sa.VARCHAR(), nullable=False)
