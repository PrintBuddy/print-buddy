from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Numeric
from datetime import datetime
from enum import Enum
import uuid

from ...core.utils import generate_time


class TransactionType(str, Enum):
    ADJUSTMENT = "adjustment"
    RECHARGE = "recharge"
    REFUND = "refund"
    PRINT = "print"
    EXPENSE = "expense"
    PRODUCT_PURCHASE = "product_purchase"
    FREE_REPRINT = "free_reprint"


class ActorType(str, Enum):
    """Who authorized a transaction — distinct from *how* they reached the
    system (e.g. an admin recharging via the Telegram bot is still an ADMIN
    actor; TELEGRAM_BOT is reserved for actions the bot itself initiates
    with no human admin behind them, which don't exist yet but keep the
    enum ready for that case)."""
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    SYSTEM = "system"
    TELEGRAM_BOT = "telegram_bot"


class Transaction(SQLModel, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True
    )

    # Nullable: an EXPENSE row doesn't affect any user's balance at all —
    # it's money leaving the pool to buy supplies, not moving to/from a
    # user. Every other transaction type still always sets this.
    user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", ondelete="CASCADE", index=True)

    type: TransactionType = Field(
        nullable=False
    )

    # Negative for outflows (PRINT debits, EXPENSE), positive for inflows
    # (RECHARGE, REFUND); sign convention already established by PRINT
    # before EXPENSE existed.
    amount: float = Field(
        sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False)
    )

    # Null for EXPENSE rows — there's no user balance for "after" to mean
    # anything.
    balance_after: float | None = Field(
        default=None, sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=True)
    )

    note: str = Field(nullable=True)

    # Structured attribution — who authorized this, replacing the old
    # practice of parsing an admin's username back out of `note`. Nullable
    # because historical rows predate these columns and can't be
    # reliably backfilled from free text.
    actor_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL", index=True
    )
    actor_type: ActorType | None = Field(default=None, nullable=True)
    target_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL", index=True
    )

    related_recharge_request_id: uuid.UUID | None = Field(
        default=None, foreign_key="rechargerequest.id", ondelete="SET NULL"
    )
    related_refund_request_id: uuid.UUID | None = Field(
        default=None, foreign_key="refundrequest.id", ondelete="SET NULL"
    )
    related_job_id: uuid.UUID | None = Field(
        default=None, foreign_key="printjob.id", ondelete="SET NULL"
    )
    related_expense_id: uuid.UUID | None = Field(
        default=None, foreign_key="expense.id", ondelete="SET NULL"
    )
    related_product_id: uuid.UUID | None = Field(
        default=None, foreign_key="product.id", ondelete="SET NULL"
    )

    # Set once a Super Admin sweeps this row's cash/transfer recharge out
    # of the admin's hands — null means "still outstanding". Only ever
    # meaningful on RECHARGE rows with actor_type=ADMIN/SUPER_ADMIN.
    collected_in_event_id: uuid.UUID | None = Field(
        default=None, foreign_key="collectionevent.id", ondelete="SET NULL", index=True
    )

    created_at: datetime = Field(
        nullable=False,
        default_factory=generate_time
    )
