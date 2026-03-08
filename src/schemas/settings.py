from pydantic import BaseModel
from datetime import datetime


class CashContact(BaseModel):
    name: str
    number: str


class BankInfo(BaseModel):
    name: str
    iban: str
    link: str


class ConfirmationContact(BaseModel):
    name: str
    number: str


class RechargeInfoSchema(BaseModel):
    cashContacts: list[CashContact]
    bank: BankInfo
    confirmation: ConfirmationContact


class TelegramAdminRead(BaseModel):
    id: str
    telegram_id: str
    user_id: str
    username: str | None = None
    name: str | None = None
    surname: str | None = None


class TelegramAdminCreate(BaseModel):
    username: str   # app username used to look up the PrintBuddy user
    telegram_id: str


class TonerAlertConfig(BaseModel):
    enabled: bool = False
    interval_hours: int = 24  # hours between repeat notifications while toner is still low


class ActivityLogEntry(BaseModel):
    id: str
    action: str  # "recharge" | "adjustment" | "refund_approved" | "refund_denied"
    admin_username: str | None = None
    target_username: str | None = None
    amount: float | None = None
    balance_after: float | None = None
    note: str | None = None
    created_at: datetime
