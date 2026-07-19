from datetime import datetime
from pydantic import BaseModel, Field
import uuid

from ..db.models.expense import ExpenseCategory


class ExpenseCreate(BaseModel):
    category: ExpenseCategory
    amount: float = Field(..., gt=0)
    description: str | None = None
    receipt_file_id: uuid.UUID | None = None


class ExpenseRead(BaseModel):
    id: uuid.UUID
    category: ExpenseCategory
    amount: float
    description: str | None = None
    recorded_by_admin_id: uuid.UUID | None = None
    receipt_file_id: uuid.UUID | None = None
    created_at: datetime
