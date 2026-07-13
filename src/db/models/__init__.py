from .user import User
from .printer import Printer
from .printerjob import PrintJob
from .file import File
from .transaction import Transaction
from .telegram_admin import TelegramAdmin
from .refund_request import RefundRequest
from .recharge_request import RechargeRequest
from .app_config import AppConfig
from .group import Group, UserGroup, GroupPrinterPermit

# Re-exported so importing this package (as migrations/env.py does, for
# Alembic autogenerate) registers every model on SQLModel.metadata.
__all__ = [
    "User",
    "Printer",
    "PrintJob",
    "File",
    "Transaction",
    "TelegramAdmin",
    "RefundRequest",
    "RechargeRequest",
    "AppConfig",
    "Group",
    "UserGroup",
    "GroupPrinterPermit",
]
