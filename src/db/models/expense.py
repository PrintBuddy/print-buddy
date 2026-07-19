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

    recorded_by_admin_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL", index=True
    )
    receipt_file_id: uuid.UUID | None = Field(
        default=None, foreign_key="file.id", ondelete="SET NULL"
    )

    created_at: datetime = Field(default_factory=generate_time, nullable=False)
