from datetime import datetime
from enum import Enum
import uuid

from pydantic import BaseModel


class TelegramID(BaseModel):
    chat_id: str


class GenerateVoucher(TelegramID):
    amount: float


class UserBalance(TelegramID):
    username: str
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
    amount: float
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
