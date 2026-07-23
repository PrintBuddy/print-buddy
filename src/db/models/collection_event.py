from datetime import datetime
from enum import Enum
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Numeric
import uuid

from ...core.utils import generate_time


class CollectionDirection(str, Enum):
    # Admin owed the house (net recharges held), swept via "collect".
    FROM_ADMIN = "from_admin"
    # House owed the admin (expenses they fronted exceeded what they
    # owed), swept via "pay admin back".
    TO_ADMIN = "to_admin"


class CollectionEvent(SQLModel, table=True):
    """A Super Admin settling the net cash/transfer float an individual
    admin is currently holding — in either direction. Created once per
    "collect from admin X" / "pay admin X back" action; every Transaction
    row it settles gets its collected_in_event_id set to this row's id in
    the same DB transaction, so "what's still unsettled" is answered by a
    plain join rather than a separate settlement-period date range."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    super_admin_id: uuid.UUID = Field(foreign_key="user.id", ondelete="SET NULL", nullable=True, index=True)
    standard_admin_id: uuid.UUID = Field(foreign_key="user.id", ondelete="SET NULL", nullable=True, index=True)

    # Always a positive magnitude — which way it moved is `direction`.
    amount_collected: float = Field(
        sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False)
    )
    direction: CollectionDirection = Field(default=CollectionDirection.FROM_ADMIN, nullable=False)

    created_at: datetime = Field(default_factory=generate_time, nullable=False)
