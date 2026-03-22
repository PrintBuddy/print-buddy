from datetime import datetime
from enum import Enum
import uuid

from sqlmodel import Field, SQLModel

from ...core.utils import generate_time


class RechargeRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RechargeRequest(SQLModel, table=True):
    __tablename__ = "rechargerequest"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE", nullable=False, index=True)
    username: str = Field(nullable=False)
    amount: float = Field(nullable=False)
    status: RechargeRequestStatus = Field(default=RechargeRequestStatus.PENDING, nullable=False)
    requester_chat_id: str = Field(nullable=False, index=True)
    requester_telegram_username: str = Field(nullable=True, default=None)
    requester_first_name: str = Field(nullable=True, default=None)
    requester_last_name: str = Field(nullable=True, default=None)
    resolved_by_username: str = Field(nullable=True, default=None)
    created_at: datetime = Field(default_factory=generate_time, nullable=False)
    updated_at: datetime = Field(
        default_factory=generate_time,
        nullable=False,
        sa_column_kwargs={"onupdate": generate_time},
    )
