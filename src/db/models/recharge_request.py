from datetime import datetime
from enum import Enum
import uuid

from sqlmodel import Field, SQLModel

from ...core.utils import generate_time


class RechargeRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RechargeMethod(str, Enum):
    CASH = "cash"
    TRANSFER = "transfer"


class RechargeRequest(SQLModel, table=True):
    __tablename__ = "rechargerequest"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE", nullable=False, index=True)
    username: str = Field(nullable=False)
    amount: float = Field(nullable=False)
    message: str = Field(nullable=True, default=None)
    status: RechargeRequestStatus = Field(default=RechargeRequestStatus.PENDING, nullable=False)

    # Populated for bot-created requests only (the bot conversation always
    # has a Telegram chat behind it); null for web-created ones, which
    # authenticate via JWT instead.
    requester_chat_id: str = Field(nullable=True, default=None, index=True)
    requester_telegram_username: str = Field(nullable=True, default=None)
    requester_first_name: str = Field(nullable=True, default=None)
    requester_last_name: str = Field(nullable=True, default=None)

    # Which admin the requester says they paid, and how. Null for legacy
    # bot-created requests, which still broadcast to every TelegramAdmin
    # rather than target one.
    method: RechargeMethod = Field(nullable=True, default=None)
    target_telegram_admin_id: uuid.UUID | None = Field(
        default=None, foreign_key="telegramadmin.id", ondelete="SET NULL"
    )

    # Tracks the single Telegram notification sent for this request (by
    # whichever side sent it — the backend directly, for web-created
    # requests) so it can be edited in place once resolved, regardless of
    # which channel (web or Telegram) does the resolving. Replaces the old
    # in-memory-only tracking, which didn't survive a bot restart.
    notified_chat_id: str = Field(nullable=True, default=None)
    notified_message_id: int = Field(nullable=True, default=None)

    resolved_by_username: str = Field(nullable=True, default=None)
    created_at: datetime = Field(default_factory=generate_time, nullable=False)
    updated_at: datetime = Field(
        default_factory=generate_time,
        nullable=False,
        sa_column_kwargs={"onupdate": generate_time},
    )
