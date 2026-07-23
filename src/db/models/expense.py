from datetime import datetime
from enum import Enum
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Numeric
import uuid

from ...core.utils import generate_time


class ExpenseCategory(str, Enum):
    TONER = "toner"
    PAPER = "paper"
    MAINTENANCE = "maintenance"
    OTHER = "other"


class Expense(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    category: ExpenseCategory = Field(nullable=False)
    amount: float = Field(
        sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False)
    )
    description: str = Field(nullable=True, default=None)

    # Who entered this into the system — may differ from who actually paid.
    recorded_by_admin_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL", index=True
    )
    # Who fronted the money out of pocket — this is who the house owes (or
    # is owed by, netted against recharges they've collected) for this
    # expense, and what the mirrored Transaction's actor_id is set from.
    # Defaults to recorded_by_admin_id when not given explicitly.
    paid_by_admin_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL", index=True
    )
    receipt_file_id: uuid.UUID | None = Field(
        default=None, foreign_key="file.id", ondelete="SET NULL"
    )

    created_at: datetime = Field(default_factory=generate_time, nullable=False)
