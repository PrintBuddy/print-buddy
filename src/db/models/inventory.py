from datetime import datetime
from enum import Enum
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Numeric
import uuid

from ...core.utils import generate_time


class InventoryCategory(str, Enum):
    PAPER = "paper"
    TONER_BW = "toner_bw"
    TONER_COLOR = "toner_color"
    BINDING_SUPPLY = "binding_supply"
    OTHER = "other"


class InventoryMovementReason(str, Enum):
    PURCHASE = "purchase"
    PRINT_CONSUMPTION = "print_consumption"
    MANUAL_ADJUSTMENT = "manual_adjustment"
    PRODUCT_SALE = "product_sale"  # reserved for Phase 4 (spiral binding etc.)


class InventoryItem(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    name: str = Field(nullable=False)
    category: InventoryCategory = Field(nullable=False)
    unit: str = Field(nullable=False)

    current_stock: float = Field(
        default=0.0, sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False)
    )
    low_stock_threshold: float = Field(
        default=0.0, sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False)
    )

    # Only meaningful for per-printer toner — paper is typically shared
    # across every printer, so this stays null for a general paper stock.
    printer_id: uuid.UUID | None = Field(
        default=None, foreign_key="printer.id", ondelete="SET NULL"
    )
    reorder_supplier: str | None = Field(default=None, nullable=True)

    created_at: datetime = Field(default_factory=generate_time, nullable=False)
    updated_at: datetime = Field(
        default_factory=generate_time,
        nullable=False,
        sa_column_kwargs={"onupdate": generate_time},
    )


class InventoryMovement(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    item_id: uuid.UUID = Field(foreign_key="inventoryitem.id", ondelete="CASCADE", index=True)
    delta: float = Field(
        sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False)
    )
    reason: InventoryMovementReason = Field(nullable=False)

    related_job_id: uuid.UUID | None = Field(
        default=None, foreign_key="printjob.id", ondelete="SET NULL"
    )
    related_expense_id: uuid.UUID | None = Field(
        default=None, foreign_key="expense.id", ondelete="SET NULL"
    )

    created_at: datetime = Field(default_factory=generate_time, nullable=False)
