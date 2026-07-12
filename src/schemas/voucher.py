from pydantic import BaseModel, Field
import uuid


class VoucherCreate(BaseModel):
    code: str
    amount: float = Field(..., gt=0)
    created_by_id: uuid.UUID
    created_by_name: str


class VoucherRead(BaseModel):
    code: str
    amount: float


class VoucherRedeem(BaseModel):
    code: str
    redeemed_by_id: uuid.UUID
    redeemed_by_name: str
    

class RedeemSuccess(BaseModel):
    success: bool
