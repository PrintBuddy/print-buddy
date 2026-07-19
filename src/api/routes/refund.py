import uuid

from fastapi import APIRouter, status, HTTPException

from ..dependencies.token import TokenDep, AdminTokenDep
from ..dependencies.database import SessionDep
from ..dependencies.pagination import PaginationDep

from ...db.crud.refund_request import RefundRequestService
from ...db.crud.printjob import PrintJobService
from ...db.crud.user import UserService
from ...db.crud.transaction import TransactionService
from ...db.models.printerjob import JobStatus
from ...db.models.refund_request import RefundStatus
from ...schemas.refund import (
    RefundRequestCreate,
    RefundRequestAdminUpdate,
    RefundRequestRead,
    RefundRequestAdminRead
)
from ...schemas.transaction import TransactionCreate
from ...db.models.transaction import TransactionType, ActorType


router = APIRouter()

refund_service = RefundRequestService()
pj_service = PrintJobService()
user_service = UserService()
tx_service = TransactionService()


# ─── User endpoints ──────────────────────────────────────────────────────────

@router.post(
    "/{job_id}",
    response_model=RefundRequestRead,
    status_code=status.HTTP_201_CREATED
)
def request_refund(
    job_id: str,
    data: RefundRequestCreate,
    token: TokenDep,
    session: SessionDep
):
    """Create a refund request for a completed print job."""
    user_id = token.credentials

    job = pj_service.get_job_by_id(job_id, session)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Print job not found"
        )

    if str(job.user_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this print job"
        )

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only completed print jobs can be refunded"
        )

    existing = refund_service.get_refund_by_job_id(job_id, session)
    if existing is not None:
        if existing.status == RefundStatus.DENIED:
            # Allow re-requesting by removing the denied request
            refund_service.delete_refund_request(str(existing.id), session)
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A refund request already exists for this print job"
            )

    refund = refund_service.create_refund_request(user_id, job_id, data, session)
    return refund


@router.get(
    "/me",
    response_model=list[RefundRequestRead],
    status_code=status.HTTP_200_OK
)
def get_my_refunds(
    token: TokenDep,
    session: SessionDep,
    pagination: PaginationDep
):
    """Get all refund requests made by the current user."""
    user_id = token.credentials
    return refund_service.get_refunds_by_user(user_id, session, pagination.limit, pagination.offset)


# ─── Admin endpoints ──────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[RefundRequestAdminRead],
    status_code=status.HTTP_200_OK
)
def get_all_refunds(
    token: AdminTokenDep,
    session: SessionDep,
    pagination: PaginationDep
):
    """Get all refund requests (admin only)."""
    return refund_service.get_all_refunds(session, pagination.limit, pagination.offset)


@router.get(
    "/pending",
    response_model=list[RefundRequestAdminRead],
    status_code=status.HTTP_200_OK
)
def get_pending_refunds(
    token: AdminTokenDep,
    session: SessionDep,
    pagination: PaginationDep
):
    """Get all pending refund requests (admin only)."""
    return refund_service.get_pending_refunds(session, pagination.limit, pagination.offset)


@router.patch(
    "/{refund_id}",
    response_model=RefundRequestAdminRead,
    status_code=status.HTTP_200_OK
)
def resolve_refund(
    refund_id: str,
    data: RefundRequestAdminUpdate,
    token: AdminTokenDep,
    session: SessionDep
):
    """Approve or deny a refund request (admin only).
    When approved the print job cost is refunded to the user's balance."""
    admin_id = token.credentials

    refund = refund_service.get_refund_by_id(refund_id, session)
    if refund is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refund request not found"
        )

    if refund.status != RefundStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This refund request has already been resolved"
        )

    if data.status not in (RefundStatus.APPROVED, RefundStatus.DENIED):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Status must be 'approved' or 'denied'"
        )

    admin_username = user_service.get_username_by_id(admin_id, session)

    # If approved, credit the user *before* the request is marked resolved —
    # a failed credit should not leave a refund marked approved with no
    # money actually moved.
    tx_data = None
    if data.status == RefundStatus.APPROVED:
        job = pj_service.get_job_by_id(str(refund.print_job_id), session)
        if job is not None:
            result = user_service.adjust_balance(
                str(refund.user_id), job.cost, session, enforce_credit_limit=False
            )
            if not result.ok:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            tx_data = TransactionCreate(
                user_id=refund.user_id,
                type=TransactionType.REFUND,
                amount=job.cost,
                balance_after=result.new_balance,  # type: ignore
                note=f"Refund approved by {admin_username} for job {job.file_name}",
                actor_id=uuid.UUID(admin_id),
                actor_type=ActorType.ADMIN,
                target_user_id=refund.user_id,
                related_refund_request_id=refund.id,
                related_job_id=job.id,
            )

    updated = refund_service.update_refund_request(refund_id, data, session, resolved_by_username=admin_username)

    if tx_data is not None:
        tx_service.create_transaction(tx_data, session)

    return updated
