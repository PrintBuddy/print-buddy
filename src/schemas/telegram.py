from datetime import datetime
from enum import Enum
import uuid

from pydantic import BaseModel, Field


class TelegramID(BaseModel):
    chat_id: str


class UserBalance(TelegramID):
    username: str
    # Reused by both /recharge (must be > 0) and /balance-adjust (an
    # absolute target, legitimately 0) — left unconstrained here;
    # adjust_balance's own atomic update guards the outcome either way.
    amount: float


class RechargeRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RechargeRequestAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class TelegramRechargeRequestCreate(TelegramID):
    username: str
    amount: float = Field(..., gt=0)
    message: str | None = None
    telegram_username: str | None = None
    telegram_first_name: str | None = None
    telegram_last_name: str | None = None


class TelegramRechargeRequestResolve(TelegramID):
    action: RechargeRequestAction


class TelegramRechargeRequestRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    username: str
    amount: float
    message: str | None = None
    status: RechargeRequestStatus
    requester_chat_id: str
    requester_telegram_username: str | None = None
    requester_first_name: str | None = None
    requester_last_name: str | None = None
    resolved_by_username: str | None = None
    created_at: datetime
    updated_at: datetime


class TelegramRechargeRequestResult(BaseModel):
    request: TelegramRechargeRequestRead
    admin_chat_ids: list[str]
    user_name: str
    user_surname: str
