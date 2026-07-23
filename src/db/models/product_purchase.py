from datetime import datetime
from enum import Enum
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Numeric
import uuid

from ...core.utils import generate_time


class ProductPurchaseStatus(str, Enum):
    PENDING = "pending"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"


class ProductPurchase(SQLModel, table=True):
    """A user buying an extra (spiral binding, etc.). Money is taken up
    front at creation — PENDING means "paid, not yet handed over" — so a
    REJECTED resolution always refunds; FULFILLED never does."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE", nullable=False, index=True)
    username: str = Field(nullable=False)

    product_id: uuid.UUID | None = Field(default=None, foreign_key="product.id", ondelete="SET NULL")
    # Denormalized so the purchase's own record stays meaningful even if
    # the product is later renamed or deactivated.
    product_name: str = Field(nullable=False)

    quantity: int = Field(nullable=False, default=1)
    unit_price: float = Field(sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False))
    total_amount: float = Field(sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False))

    message: str = Field(nullable=True, default=None)
    status: ProductPurchaseStatus = Field(default=ProductPurchaseStatus.PENDING, nullable=False)

    admin_message: str = Field(nullable=True, default=None)
    resolved_by_username: str = Field(nullable=True, default=None)

    created_at: datetime = Field(default_factory=generate_time, nullable=False)
    updated_at: datetime = Field(
        default_factory=generate_time,
        nullable=False,
        sa_column_kwargs={"onupdate": generate_time},
    )


class ProductPurchaseNotification(SQLModel, table=True):
    """One row per admin actually notified on Telegram about a purchase —
    unlike a recharge request (one targeted admin), a purchase broadcasts
    to every admin, so resolving it has to edit every message sent, not
    just one."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    purchase_id: uuid.UUID = Field(foreign_key="productpurchase.id", ondelete="CASCADE", index=True)
    chat_id: str = Field(nullable=False)
    message_id: int = Field(nullable=False)
