from pydantic import BaseModel
from datetime import datetime
import uuid

from ..db.models.refund_request import RefundStatus


class RefundRequestCreate(BaseModel):
    message: str | None = None


class RefundRequestAdminUpdate(BaseModel):
    status: RefundStatus
    admin_message: str | None = None


class RefundRequestRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    print_job_id: uuid.UUID
    message: str | None = None
    status: RefundStatus
    admin_message: str | None = None
    resolved_by_username: str | None = None
    created_at: datetime
    updated_at: datetime


class RefundRequestAdminRead(RefundRequestRead):
    """Extended read for admins — includes the same fields but is
    semantically distinct, allowing richer data to be added later."""
    pass
