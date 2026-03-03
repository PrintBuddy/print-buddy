"""Added refund request table

Revision ID: a3f7c1d2e5b8
Revises: 193a9d72a2e3
Create Date: 2026-03-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a3f7c1d2e5b8'
down_revision: Union[str, Sequence[str], None] = '193a9d72a2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'refundrequest',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('print_job_id', sa.Uuid(), nullable=False),
        sa.Column('message', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='pending'),
        sa.Column('admin_message', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['print_job_id'], ['printjob.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refundrequest_id'), 'refundrequest', ['id'], unique=False)
    op.create_index(op.f('ix_refundrequest_user_id'), 'refundrequest', ['user_id'], unique=False)
    op.create_index(op.f('ix_refundrequest_print_job_id'), 'refundrequest', ['print_job_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_refundrequest_print_job_id'), table_name='refundrequest')
    op.drop_index(op.f('ix_refundrequest_user_id'), table_name='refundrequest')
    op.drop_index(op.f('ix_refundrequest_id'), table_name='refundrequest')
    op.drop_table('refundrequest')
