from pydantic import BaseModel


class PrinterPageStats(BaseModel):
    printer_name: str
    total_pages: int
    bw_pages: int
    color_pages: int
    total_sheets: int
    total_cost: float


class UserPageStats(BaseModel):
    user_id: str
    username: str
    total_pages: int
    bw_pages: int
    color_pages: int
    total_sheets: int


class FinanceStats(BaseModel):
    total_recharged: float
    total_current_balance: float
    total_spent_on_print: float
    total_refunded: float
    total_adjustments: float


class GlobalStats(BaseModel):
    total_pages: int
    bw_pages: int
    color_pages: int
    total_sheets: int
    total_jobs: int
    by_printer: list[PrinterPageStats]
    by_user: list[UserPageStats]
    finance: FinanceStats


class UserPersonalStats(BaseModel):
    total_pages: int
    bw_pages: int
    color_pages: int
    total_sheets: int
    total_jobs: int
    total_spent: float
    by_printer: list[PrinterPageStats]
