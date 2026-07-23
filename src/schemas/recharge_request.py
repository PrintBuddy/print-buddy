from datetime import datetime
from pydantic import BaseModel, Field
import uuid

from ..db.models.recharge_request import RechargeRequestStatus, RechargeMethod


class RechargeAdminOption(BaseModel):
    """One entry in the "who did you pay" picker — deliberately excludes
    the admin's Telegram chat_id, which the frontend never needs. Also
    doubles as the "how to recharge" info shown on the Balance page:
    phone_number is always set (every admin takes cash), the bank fields
    are only meaningful when accepts_transfer is true."""
    telegram_admin_id: uuid.UUID
    username: str
    name: str
    surname: str
    phone_number: str | None = None
    accepts_transfer: bool = False
    bank_name: str | None = None
    bank_iban: str | None = None
    bank_link: str | None = None


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
    target_admin_username: str | None = None
    target_admin_name: str | None = None
    target_admin_surname: str | None = None
    resolved_by_username: str | None = None
    created_at: datetime
    updated_at: datetime


class RechargeRequestAdminRead(RechargeRequestRead):
    user_id: uuid.UUID
    username: str
