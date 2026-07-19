from datetime import datetime
from pydantic import BaseModel, Field
import uuid

from ..db.models.recharge_request import RechargeRequestStatus, RechargeMethod


class RechargeAdminOption(BaseModel):
    """One entry in the "who did you pay" picker — deliberately excludes
    the admin's Telegram chat_id, which the frontend never needs."""
    telegram_admin_id: uuid.UUID
    username: str
    name: str
    surname: str


class RechargeRequestCreate(BaseModel):
    amount: float = Field(..., gt=0)
    method: RechargeMethod
    target_telegram_admin_id: uuid.UUID
    message: str | None = None


class RechargeRequestResolve(BaseModel):
    status: RechargeRequestStatus

    def validate_actionable(self):
        if self.status not in (RechargeRequestStatus.APPROVED, RechargeRequestStatus.REJECTED):
            raise ValueError("Status must be 'approved' or 'rejected'")


class RechargeRequestRead(BaseModel):
    id: uuid.UUID
    amount: float
    method: RechargeMethod | None = None
    message: str | None = None
    status: RechargeRequestStatus
    resolved_by_username: str | None = None
    created_at: datetime
    updated_at: datetime


class RechargeRequestAdminRead(RechargeRequestRead):
    user_id: uuid.UUID
    username: str
