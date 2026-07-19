from datetime import datetime
from pydantic import BaseModel, Field
import uuid

from ..db.models.inventory import InventoryCategory, InventoryMovementReason
from ..db.models.expense import ExpenseCategory


class InventoryItemCreate(BaseModel):
    name: str
    category: InventoryCategory
    unit: str
    initial_stock: float = 0.0
    low_stock_threshold: float = Field(default=0.0, ge=0)
    printer_id: uuid.UUID | None = None
    reorder_supplier: str | None = None


class InventoryItemRead(BaseModel):
    id: uuid.UUID
    name: str
    category: InventoryCategory
    unit: str
    current_stock: float
    low_stock_threshold: float
    printer_id: uuid.UUID | None = None
    reorder_supplier: str | None = None
    is_low_stock: bool
    created_at: datetime
    updated_at: datetime


class InventoryMovementCreate(BaseModel):
    delta: float
    reason: InventoryMovementReason


class InventoryMovementRead(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    delta: float
    reason: InventoryMovementReason
    related_job_id: uuid.UUID | None = None
    related_expense_id: uuid.UUID | None = None
    created_at: datetime


class RestockRequest(BaseModel):
    """One submit that both logs the purchase as an Expense and records the
    stock increase, so the two don't become disconnected manual steps."""
    quantity: float = Field(..., gt=0)
    expense_category: ExpenseCategory
    expense_amount: float = Field(..., gt=0)
    expense_description: str | None = None
