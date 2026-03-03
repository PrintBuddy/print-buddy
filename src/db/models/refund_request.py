from sqlmodel import SQLModel, Field
from enum import Enum
from datetime import datetime
import uuid

from ...core.utils import generate_time


class RefundStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class RefundRequest(SQLModel, table=True):
    __tablename__ = "refundrequest"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True
    )

    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE", nullable=False)

    print_job_id: uuid.UUID = Field(foreign_key="printjob.id", ondelete="CASCADE", nullable=False)

    message: str = Field(nullable=True, default=None)

    status: RefundStatus = Field(default=RefundStatus.PENDING, nullable=False)

    admin_message: str = Field(nullable=True, default=None)

    resolved_by_username: str = Field(nullable=True, default=None)

    created_at: datetime = Field(
        default_factory=generate_time,
        nullable=False
    )

    updated_at: datetime = Field(
        default_factory=generate_time,
        nullable=False,
        sa_column_kwargs={
            "onupdate": generate_time
        }
    )
