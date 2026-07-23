from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
import uuid

from ..db.models.product_purchase import ProductPurchaseStatus


class ProductPurchaseCreate(BaseModel):
    quantity: int = Field(default=1, ge=1)
    message: str | None = None


class ProductPurchaseResolve(BaseModel):
    action: Literal["fulfill", "reject"]
    admin_message: str | None = None


class ProductPurchaseRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID | None = None
    product_name: str
    quantity: int
    unit_price: float
    total_amount: float
    message: str | None = None
    status: ProductPurchaseStatus
    admin_message: str | None = None
    resolved_by_username: str | None = None
    created_at: datetime
    updated_at: datetime


class ProductPurchaseAdminRead(ProductPurchaseRead):
    user_id: uuid.UUID
    username: str
