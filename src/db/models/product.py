from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Numeric
import uuid

from ...core.utils import generate_time


class Product(SQLModel, table=True):
    """A purchasable extra (spiral binding today; generalized so a future
    add-on like lamination doesn't need another schema change)."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    name: str = Field(nullable=False)
    price: float = Field(
        sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False)
    )
    is_active: bool = Field(default=True, nullable=False)

    # Optional — not every product needs stock tracking, but spiral
    # binding does once an admin sets up a "Binding Supply" InventoryItem.
    inventory_item_id: uuid.UUID | None = Field(
        default=None, foreign_key="inventoryitem.id", ondelete="SET NULL"
    )

    created_at: datetime = Field(default_factory=generate_time, nullable=False)
    updated_at: datetime = Field(
        default_factory=generate_time,
        nullable=False,
        sa_column_kwargs={"onupdate": generate_time},
    )
