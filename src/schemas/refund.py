from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from ..db.models.refund_request import RefundStatus


class RefundRequestCreate(BaseModel):
    message: str | None = None


class RefundRequestAdminUpdate(BaseModel):
    status: RefundStatus
    admin_message: str | None = None


class RefundOverrideCreate(BaseModel):
    """Mandatory reason — unlike admin_message on the normal approve/deny
    flow, an override has no user request behind it to provide context,
    so the reason is the only accountability trail."""
    reason: str = Field(..., min_length=1)


class RefundRequestRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    print_job_id: uuid.UUID
    message: str | None = None
    status: RefundStatus
    admin_message: str | None = None
    initiated_by_admin_id: uuid.UUID | None = None
    resolved_by_username: str | None = None
    created_at: datetime
    updated_at: datetime


class RefundRequestAdminRead(RefundRequestRead):
    """Extended read for admins — includes the same fields but is
    semantically distinct, allowing richer data to be added later."""
    pass
