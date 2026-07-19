from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
import uuid


class ProductCreate(BaseModel):
    name: str
    price: float = Field(..., gt=0)
    inventory_item_id: uuid.UUID | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    price: float | None = Field(default=None, gt=0)
    is_active: bool | None = None
    inventory_item_id: uuid.UUID | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    price: float
    is_active: bool
    inventory_item_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class ProductPurchaseResult(BaseModel):
    product: ProductRead
    new_balance: float
