from datetime import datetime
from pydantic import BaseModel
import uuid

from ..db.models.collection_event import CollectionDirection


class OutstandingAdminFloat(BaseModel):
    admin_id: uuid.UUID
    username: str
    name: str
    surname: str
    # Signed: positive = admin owes the house (recharges collected minus
    # any expenses they've fronted), negative = the house owes the admin.
    net_amount: float


class CollectionEventRead(BaseModel):
    id: uuid.UUID
    super_admin_id: uuid.UUID | None = None
    super_admin_username: str | None = None
    standard_admin_id: uuid.UUID | None = None
    standard_admin_username: str | None = None
    amount_collected: float
    direction: CollectionDirection
    created_at: datetime
