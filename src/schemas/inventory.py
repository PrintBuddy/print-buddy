from datetime import datetime
from pydantic import BaseModel, Field
import uuid

from ..db.models.inventory import InventoryCategory, InventoryMovementReason


class InventoryItemCreate(BaseModel):
    name: str
    category: InventoryCategory
    unit: str
    initial_stock: float = 0.0
    low_stock_threshold: float = Field(default=0.0, ge=0)
    printer_id: uuid.UUID | None = None
    reorder_supplier: str | None = None


class InventoryItemUpdate(BaseModel):
    name: str | None = None
    category: InventoryCategory | None = None
    unit: str | None = None
    low_stock_threshold: float | None = Field(default=None, ge=0)
    printer_id: uuid.UUID | None = None
    reorder_supplier: str | None = None
    is_active: bool | None = None


class InventoryItemRead(BaseModel):
    id: uuid.UUID
    name: str
    category: InventoryCategory
    unit: str
    current_stock: float
    low_stock_threshold: float
    printer_id: uuid.UUID | None = None
    reorder_supplier: str | None = None
    is_active: bool
    is_low_stock: bool
    created_at: datetime
    updated_at: datetime


class InventoryMovementCreate(BaseModel):
    delta: float
    reason: InventoryMovementReason
    notes: str | None = None


class InventoryMovementRead(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    delta: float
    reason: InventoryMovementReason
    notes: str | None = None
    related_job_id: uuid.UUID | None = None
    related_expense_id: uuid.UUID | None = None
    created_at: datetime


class RestockRequest(BaseModel):
    """Records new stock arriving. Deliberately doesn't touch Expense —
    the purchase is usually logged separately, days before the package
    actually arrives; use the Log Expense flow for the cost."""
    quantity: float = Field(..., gt=0)
