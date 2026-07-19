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

    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE", nullable=False, index=True)

    print_job_id: uuid.UUID = Field(foreign_key="printjob.id", ondelete="CASCADE", nullable=False, index=True)

    message: str = Field(nullable=True, default=None)

    status: RefundStatus = Field(default=RefundStatus.PENDING, nullable=False)

    admin_message: str = Field(nullable=True, default=None)

    # Set only for admin-initiated overrides (refunding a job the user
    # never requested a refund for) — null for the normal user-request ->
    # admin-approve flow. Distinguishes the two without needing a second
    # status value.
    initiated_by_admin_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )

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
