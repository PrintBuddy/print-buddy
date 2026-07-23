from datetime import datetime
from enum import Enum
import uuid

from pydantic import BaseModel, Field

from ..db.models.expense import ExpenseCategory


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
    requester_chat_id: str | None = None
    requester_telegram_username: str | None = None
    requester_first_name: str | None = None
    requester_last_name: str | None = None
    resolved_by_username: str | None = None
    created_at: datetime
    updated_at: datetime
    # Only set for requests created from the web app — lets the bot fall
    # back to editing this single message in place when its own in-memory
    # broadcast tracking has nothing for this request_id.
    notified_chat_id: str | None = None
    notified_message_id: int | None = None


class TelegramRechargeRequestResult(BaseModel):
    request: TelegramRechargeRequestRead
    admin_chat_ids: list[str]
    user_name: str
    user_surname: str


class ProductPurchaseAction(str, Enum):
    FULFILL = "fulfill"
    REJECT = "reject"


class ProductPurchaseStatus(str, Enum):
    PENDING = "pending"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"


class TelegramProductPurchaseResolve(TelegramID):
    action: ProductPurchaseAction


class TelegramProductPurchaseRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    username: str
    product_name: str
    quantity: int
    total_amount: float
    message: str | None = None
    status: ProductPurchaseStatus
    admin_message: str | None = None
    resolved_by_username: str | None = None
    created_at: datetime
    updated_at: datetime


class TelegramStockAdjust(TelegramID):
    item_name: str
    delta: float


class TelegramExpenseCreate(TelegramID):
    category: ExpenseCategory
    amount: float = Field(..., gt=0)
    description: str | None = None


class TelegramPurchaseNotification(BaseModel):
    chat_id: str
    message_id: int


class TelegramProductPurchaseResult(BaseModel):
    purchase: TelegramProductPurchaseRead
    # Every admin who was notified about this purchase — unlike a recharge
    # request's single target admin, the bot has to edit one message per
    # admin here, since the purchase was broadcast to all of them.
    notifications: list[TelegramPurchaseNotification]
