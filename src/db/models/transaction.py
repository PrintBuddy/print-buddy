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


class Transaction(SQLModel, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True
    )

    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE", index=True)

    type: TransactionType = Field(
        nullable=False
    )

    amount: float = Field(
        sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False)
    )

    balance_after: float = Field(
        sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False)
    )

    note: str = Field(nullable=True)

    created_at: datetime = Field(
        nullable=False,
        default_factory=generate_time
    )