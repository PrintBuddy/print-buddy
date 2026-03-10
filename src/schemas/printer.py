from pydantic import BaseModel, field_validator
from datetime import datetime

from ..db.models.printer import PrinterStatus


class PrinterCreate(BaseModel):
    name: str
    location: str
    status: PrinterStatus


class PrinterCUPSUpdate(BaseModel):
    name: str
    location: str
    status: PrinterStatus
    state_reasons: list[str] = []


class PrinterRead(BaseModel):
    name: str
    location: str
    status: PrinterStatus
    state_reasons: list[str] = []
    price_per_page_bw: float
    admits_color: bool
    price_per_page_color: float
    is_active: bool
    updated_at: datetime

    @field_validator("state_reasons", mode="before")
    @classmethod
    def coerce_none_to_empty(cls, v):
        return v if v is not None else []


class PrinterAdminUpdate(BaseModel):
    price_per_page_bw: float | None = None
    admits_color: bool | None = None
    price_per_page_color: float | None = None
    is_active: bool | None = None


class TonerMarker(BaseModel):
    name: str
    color: str | None = None
    level: int               # -1 means the driver cannot report a value
    low_level: int
    high_level: int
    marker_type: str | None = None  # e.g. "toner", "ink", "drum", etc.
