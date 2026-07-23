"""Ledger and role overhaul: structured transaction attribution + user roles

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-07-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a4b5c6d7e8f9'
down_revision: Union[str, Sequence[str], None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- User roles: replace is_admin bool with a 3-tier role enum ---
    # sa.Enum used inline in add_column does NOT auto-create the Postgres
    # type the way it does inside create_table — it must be created
    # explicitly first, then referenced with create_type=False.
    # Labels are the Python Enum members' *names* (uppercase), matching how
    # SQLAlchemy's Enum type stores every other native enum in this schema
    # (e.g. jobstatus/printerstatus hold 'PENDING'/'IDLE', not lowercase
    # values) — confirmed against a real Postgres instance, since this is
    # exactly the kind of mismatch a raw SQLite/unit-test run can't catch.
    userrole = sa.Enum('USER', 'ADMIN', 'SUPER_ADMIN', name='userrole')
    userrole.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'user',
        sa.Column('role', sa.Enum('USER', 'ADMIN', 'SUPER_ADMIN', name='userrole', create_type=False), nullable=True),
    )
    op.execute("""
        UPDATE "user" SET role = CASE WHEN is_admin THEN 'ADMIN'::userrole ELSE 'USER'::userrole END
    """)
    op.alter_column('user', 'role', nullable=False)
    op.drop_column('user', 'is_admin')

    # --- Transaction: structured attribution (actor/target/related-entity),
    # replacing the old practice of parsing an admin's username back out of
    # `note`. Nullable throughout: historical rows predate these columns and
    # can't be reliably backfilled from free text. ---
    op.add_column('transaction', sa.Column('actor_id', sa.Uuid(), nullable=True))
    actortype = sa.Enum('USER', 'ADMIN', 'SUPER_ADMIN', 'SYSTEM', 'TELEGRAM_BOT', name='actortype')
    actortype.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'transaction',
        sa.Column(
            'actor_type',
            sa.Enum('USER', 'ADMIN', 'SUPER_ADMIN', 'SYSTEM', 'TELEGRAM_BOT', name='actortype', create_type=False),
            nullable=True,
        ),
    )
    op.add_column('transaction', sa.Column('target_user_id', sa.Uuid(), nullable=True))
    op.add_column('transaction', sa.Column('related_recharge_request_id', sa.Uuid(), nullable=True))
    op.add_column('transaction', sa.Column('related_refund_request_id', sa.Uuid(), nullable=True))
    op.add_column('transaction', sa.Column('related_job_id', sa.Uuid(), nullable=True))

    op.create_index(op.f('ix_transaction_actor_id'), 'transaction', ['actor_id'])
    op.create_index(op.f('ix_transaction_target_user_id'), 'transaction', ['target_user_id'])

    op.create_foreign_key(
        'fk_transaction_actor_id_user', 'transaction', 'user',
        ['actor_id'], ['id'], ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_transaction_target_user_id_user', 'transaction', 'user',
        ['target_user_id'], ['id'], ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_transaction_related_recharge_request_id_rechargerequest', 'transaction', 'rechargerequest',
        ['related_recharge_request_id'], ['id'], ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_transaction_related_refund_request_id_refundrequest', 'transaction', 'refundrequest',
        ['related_refund_request_id'], ['id'], ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_transaction_related_job_id_printjob', 'transaction', 'printjob',
        ['related_job_id'], ['id'], ondelete='SET NULL'
    )

    # --- Append-only enforcement: a convention-only ledger is exactly what
    # let attribution drift into unstructured note-parsing before. Block
    # UPDATE/DELETE at the DB level so this can't regress silently. ---
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_transaction_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'transaction rows are append-only and cannot be updated or deleted';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER transaction_append_only
        BEFORE UPDATE OR DELETE ON "transaction"
        FOR EACH ROW EXECUTE FUNCTION prevent_transaction_mutation();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS transaction_append_only ON \"transaction\"")
    op.execute("DROP FUNCTION IF EXISTS prevent_transaction_mutation()")

    op.drop_constraint('fk_transaction_related_job_id_printjob', 'transaction', type_='foreignkey')
    op.drop_constraint('fk_transaction_related_refund_request_id_refundrequest', 'transaction', type_='foreignkey')
    op.drop_constraint('fk_transaction_related_recharge_request_id_rechargerequest', 'transaction', type_='foreignkey')
    op.drop_constraint('fk_transaction_target_user_id_user', 'transaction', type_='foreignkey')
    op.drop_constraint('fk_transaction_actor_id_user', 'transaction', type_='foreignkey')

    op.drop_index(op.f('ix_transaction_target_user_id'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_actor_id'), table_name='transaction')

    op.drop_column('transaction', 'related_job_id')
    op.drop_column('transaction', 'related_refund_request_id')
    op.drop_column('transaction', 'related_recharge_request_id')
    op.drop_column('transaction', 'target_user_id')
    op.drop_column('transaction', 'actor_type')
    op.drop_column('transaction', 'actor_id')

    op.execute("DROP TYPE IF EXISTS actortype")

    op.add_column(
        'user',
        sa.Column('is_admin', sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.execute("""
        UPDATE "user" SET is_admin = (role != 'USER'::userrole)
    """)
    op.alter_column('user', 'is_admin', nullable=False, server_default=None)
    op.drop_column('user', 'role')

    op.execute("DROP TYPE IF EXISTS userrole")
