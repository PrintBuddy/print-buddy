from pydantic import BaseModel
from datetime import datetime
import uuid

from ..db.models.transaction import TransactionType, ActorType


class TransactionRead(BaseModel):
    id: uuid.UUID
    type: TransactionType
    amount: float
    balance_after: float | None = None
    note: str | None = None
    actor_id: uuid.UUID | None = None
    actor_type: ActorType | None = None
    target_user_id: uuid.UUID | None = None
    related_recharge_request_id: uuid.UUID | None = None
    related_refund_request_id: uuid.UUID | None = None
    related_job_id: uuid.UUID | None = None
    related_expense_id: uuid.UUID | None = None
    created_at: datetime


class TransactionCreate(BaseModel):
    user_id: uuid.UUID | None = None
    type: TransactionType
    amount: float
    balance_after: float | None = None
    note: str | None = None
    actor_id: uuid.UUID | None = None
    actor_type: ActorType | None = None
    target_user_id: uuid.UUID | None = None
    related_recharge_request_id: uuid.UUID | None = None
    related_refund_request_id: uuid.UUID | None = None
    related_job_id: uuid.UUID | None = None
    related_expense_id: uuid.UUID | None = None
