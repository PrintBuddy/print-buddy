"""Admin cash reconciliation: collection events + collected_in_event_id

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-07-19 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c6d7e8f9a0b1'
down_revision: Union[str, Sequence[str], None] = 'b5c6d7e8f9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'collectionevent',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('super_admin_id', sa.Uuid(), nullable=True),
        sa.Column('standard_admin_id', sa.Uuid(), nullable=True),
        sa.Column('amount_collected', sa.Numeric(10, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['super_admin_id'], ['user.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['standard_admin_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_collectionevent_super_admin_id'), 'collectionevent', ['super_admin_id'])
    op.create_index(op.f('ix_collectionevent_standard_admin_id'), 'collectionevent', ['standard_admin_id'])

    op.add_column('transaction', sa.Column('collected_in_event_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_transaction_collected_in_event_id'), 'transaction', ['collected_in_event_id'])
    op.create_foreign_key(
        'fk_transaction_collected_in_event_id_collectionevent',
        'transaction', 'collectionevent',
        ['collected_in_event_id'], ['id'], ondelete='SET NULL'
    )

    # The Phase-0 trigger blocked ALL updates on `transaction` — correct
    # for every column except this phase's one legitimate post-hoc
    # annotation (a Super Admin sweeping cash into a CollectionEvent).
    # CREATE OR REPLACE updates the function body in place; the existing
    # trigger (already attached to `transaction`) picks up the new
    # behavior immediately, no re-attachment needed. Every other
    # append-only table (including the new collectionevent below) keeps
    # the original all-or-nothing block.
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_transaction_mutation() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION '% rows are append-only and cannot be deleted', TG_TABLE_NAME;
            END IF;

            IF TG_TABLE_NAME = 'transaction' THEN
                IF (to_jsonb(OLD) - 'collected_in_event_id') != (to_jsonb(NEW) - 'collected_in_event_id') THEN
                    RAISE EXCEPTION 'transaction rows are append-only — only collected_in_event_id may be set after creation';
                END IF;
                RETURN NEW;
            END IF;

            RAISE EXCEPTION '% rows are append-only and cannot be updated', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # collectionevent rows are themselves append-only for the same reason
    # `transaction` is — a settlement record shouldn't be editable after
    # the fact either (no exempted column here — the whole row is fixed
    # once created).
    op.execute("""
        CREATE TRIGGER collectionevent_append_only
        BEFORE UPDATE OR DELETE ON collectionevent
        FOR EACH ROW EXECUTE FUNCTION prevent_transaction_mutation();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS collectionevent_append_only ON collectionevent")

    # Restore the original all-or-nothing behavior on `transaction` —
    # collected_in_event_id is about to be dropped, so its carve-out no
    # longer applies.
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_transaction_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'transaction rows are append-only and cannot be updated or deleted';
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.drop_constraint('fk_transaction_collected_in_event_id_collectionevent', 'transaction', type_='foreignkey')
    op.drop_index(op.f('ix_transaction_collected_in_event_id'), table_name='transaction')
    op.drop_column('transaction', 'collected_in_event_id')

    op.drop_index(op.f('ix_collectionevent_standard_admin_id'), table_name='collectionevent')
    op.drop_index(op.f('ix_collectionevent_super_admin_id'), table_name='collectionevent')
    op.drop_table('collectionevent')
