from pydantic import BaseModel
from datetime import datetime


class TelegramAdminRead(BaseModel):
    id: str
    telegram_id: str
    user_id: str
    username: str | None = None
    name: str | None = None
    surname: str | None = None
    phone_number: str | None = None
    accepts_transfer: bool = False
    bank_name: str | None = None
    bank_iban: str | None = None
    bank_link: str | None = None


class TelegramAdminCreate(BaseModel):
    username: str   # app username used to look up the PrintBuddy user
    telegram_id: str
    phone_number: str | None = None
    accepts_transfer: bool = False
    bank_name: str | None = None
    bank_iban: str | None = None
    bank_link: str | None = None


class TelegramAdminUpdate(BaseModel):
    telegram_id: str | None = None
    phone_number: str | None = None
    accepts_transfer: bool | None = None
    bank_name: str | None = None
    bank_iban: str | None = None
    bank_link: str | None = None


class TonerAlertConfig(BaseModel):
    enabled: bool = False
    interval_hours: int = 24  # hours between repeat notifications while toner is still low


class ActivityLogEntry(BaseModel):
    id: str
    action: str  # "recharge" | "adjustment" | "refund_approved" | "refund_denied" | "purchase_fulfilled" | "purchase_rejected"
    admin_username: str | None = None
    target_username: str | None = None
    amount: float | None = None
    balance_after: float | None = None
    note: str | None = None
    created_at: datetime


class ADConfigSchema(BaseModel):
    enabled: bool = False
    institution_name: str = ""
    server: str
    domain: str
    base_dn: str


class ADImportResultSchema(BaseModel):
    total_found: int
    imported_count: int
    skipped_count: int
    skipped_invalid_count: int = 0
    detail: str


class ADImportRequestSchema(BaseModel):
    username: str
    pwd: str


class ADImportCandidateSchema(BaseModel):
    username: str
    name: str
    surname: str


class ADImportPreviewSchema(BaseModel):
    total_found: int
    importable_count: int
    skipped_count: int
    skipped_invalid_count: int = 0
    candidates: list[ADImportCandidateSchema]
    detail: str
