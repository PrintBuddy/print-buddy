from pydantic import BaseModel
import uuid


class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class GroupRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None


class GroupMemberAdd(BaseModel):
    user_id: uuid.UUID


class GroupPrinterPermitCreate(BaseModel):
    printer_id: uuid.UUID
    custom_price_bw: float | None = None
    custom_price_color: float | None = None


class GroupPrinterPermitUpdate(BaseModel):
    custom_price_bw: float | None = None
    custom_price_color: float | None = None


class GroupPrinterPermitRead(BaseModel):
    printer_id: uuid.UUID
    custom_price_bw: float | None = None
    custom_price_color: float | None = None


class GroupDetailRead(GroupRead):
    members: list[uuid.UUID] = []
    printer_permits: list[GroupPrinterPermitRead] = []
