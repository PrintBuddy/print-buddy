from sqlmodel import SQLModel, Field
from datetime import datetime
import uuid

from ...core.utils import generate_time


class Group(SQLModel, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True
    )

    name: str = Field(nullable=False, unique=True, index=True)

    description: str | None = Field(default=None, nullable=True)

    created_at: datetime = Field(
        default_factory=generate_time,
        nullable=False
    )


class UserGroup(SQLModel, table=True):
    __tablename__ = "usergroup"

    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        primary_key=True,
        ondelete="CASCADE"
    )

    group_id: uuid.UUID = Field(
        foreign_key="group.id",
        primary_key=True,
        ondelete="CASCADE"
    )


class GroupPrinterPermit(SQLModel, table=True):
    __tablename__ = "groupprinterperimit"

    group_id: uuid.UUID = Field(
        foreign_key="group.id",
        primary_key=True,
        ondelete="CASCADE"
    )

    printer_id: uuid.UUID = Field(
        foreign_key="printer.id",
        primary_key=True,
        ondelete="CASCADE"
    )

    # None means "use the printer's default price"
    custom_price_bw: float | None = Field(default=None, nullable=True)
    custom_price_color: float | None = Field(default=None, nullable=True)
