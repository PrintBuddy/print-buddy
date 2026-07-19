from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Numeric
import uuid

from ...core.utils import generate_time


class CollectionEvent(SQLModel, table=True):
    """A Super Admin sweeping the cash/transfer float an individual admin
    is currently holding. Created once per "collect from admin X" action;
    every Transaction row it swept up gets its collected_in_event_id set
    to this row's id in the same DB transaction, so "which recharges have
    been collected and which are still pending" is answered by a plain
    join rather than a separate settlement-period date range."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    super_admin_id: uuid.UUID = Field(foreign_key="user.id", ondelete="SET NULL", nullable=True, index=True)
    standard_admin_id: uuid.UUID = Field(foreign_key="user.id", ondelete="SET NULL", nullable=True, index=True)

    amount_collected: float = Field(
        sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False)
    )

    created_at: datetime = Field(default_factory=generate_time, nullable=False)
