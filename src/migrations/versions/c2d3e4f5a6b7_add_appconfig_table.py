"""Add appconfig table and seed initial data

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-03-02 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import json
import uuid
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RECHARGE_INFO = {
    "cashContacts": [
        {"name": "Federico Vegni", "number": "+39 391 413 1420"},
        {"name": "Roberto Benatuil", "number": "+39 351 347 3503"}
    ],
    "bank": {
        "name": "Roberto Benatuil",
        "iban": "IT46 H036 6901 6009 6358 6399 026",
        "link": "https://revolut.me/rbenatuilv"
    },
    "confirmation": {
        "name": "Roberto Benatuil",
        "number": "+39 351 347 3503"
    }
}

# Existing telegram admin mapping from telegram_admins.json
TELEGRAM_ADMINS = {
    "1326003861": "b8e3184a-2025-41e5-96b7-21479aa2085f"
}


def upgrade() -> None:
    # Create appconfig table
    op.create_table(
        'appconfig',
        sa.Column('key', sqlmodel.sql.sqltypes.AutoString(), primary_key=True, nullable=False),
        sa.Column('value', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # Seed recharge_info
    op.execute(
        sa.text(
            "INSERT INTO appconfig (key, value, updated_at) "
            "VALUES (:key, :value, :updated_at) "
            "ON CONFLICT (key) DO NOTHING"
        ).bindparams(
            key='recharge_info',
            value=json.dumps(RECHARGE_INFO),
            updated_at=datetime.utcnow()
        )
    )

    # Migrate telegram admins from JSON into telegramadmin table (if not already present)
    bind = op.get_bind()
    for telegram_id, user_id in TELEGRAM_ADMINS.items():
        # Check if user exists
        result = bind.execute(
            sa.text("SELECT id FROM \"user\" WHERE id = :uid"),
            {"uid": user_id}
        ).fetchone()
        if result is None:
            continue  # user doesn't exist in this DB, skip

        # Check if telegram admin already exists
        existing = bind.execute(
            sa.text("SELECT id FROM telegramadmin WHERE telegram_id = :tid"),
            {"tid": telegram_id}
        ).fetchone()
        if existing is not None:
            continue  # already seeded

        bind.execute(
            sa.text(
                "INSERT INTO telegramadmin (id, user_id, telegram_id, created_at) "
                "VALUES (:id, :user_id, :telegram_id, :created_at)"
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "telegram_id": telegram_id,
                "created_at": datetime.utcnow()
            }
        )


def downgrade() -> None:
    op.drop_table('appconfig')
