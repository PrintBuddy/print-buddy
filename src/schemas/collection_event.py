from datetime import datetime
from pydantic import BaseModel
import uuid


class OutstandingAdminFloat(BaseModel):
    admin_id: uuid.UUID
    username: str
    name: str
    surname: str
    outstanding_amount: float


class CollectionEventRead(BaseModel):
    id: uuid.UUID
    super_admin_id: uuid.UUID | None = None
    super_admin_username: str | None = None
    standard_admin_id: uuid.UUID | None = None
    standard_admin_username: str | None = None
    amount_collected: float
    created_at: datetime
