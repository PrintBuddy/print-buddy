from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Numeric
from enum import Enum
from datetime import datetime
import uuid

from ...core.utils import generate_time


class JobStatus(str, Enum):
    PENDING = "pending"
    HELD = "held"
    PRINTING = "printing"
    STOPPED = "stopped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ABORTED = "aborted"


TRANSIT_STATUS = [
    JobStatus.PENDING,
    JobStatus.HELD,
    JobStatus.PRINTING,
    JobStatus.STOPPED
]

ERROR_STATUS = [
    JobStatus.ABORTED,
    JobStatus.CANCELLED
]


class PrintJob(SQLModel, table=True):

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True
    )

    cups_id: str = Field(nullable=False)

    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE", index=True)

    printer_id: uuid.UUID = Field(foreign_key="printer.id", ondelete="CASCADE", index=True)

    printer_name: str = Field(nullable=False)

    file_id: uuid.UUID = Field(foreign_key="file.id", ondelete="SET NULL", nullable=True, index=True)

    file_name: str = Field(nullable=True)

    file_size: int = Field(nullable=True)

    pages: int = Field(nullable=False, default=1)

    number_up: int = Field(nullable=False, default=1)

    two_sided: bool = Field(nullable=False, default=False)

    color: bool = Field(nullable=False, default=False)

    status: JobStatus = Field(
        default=JobStatus.PENDING,
        nullable=False
    )

    cost: float = Field(
        default=0.0,
        sa_column=Column(Numeric(10, 2, asdecimal=False), nullable=False)
    )

    created_at: datetime = Field(
        default_factory=generate_time,
        nullable=False
    )

    completed_at: datetime = Field(nullable=True, default=None)
