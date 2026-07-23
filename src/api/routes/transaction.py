from fastapi import APIRouter, status

from ..dependencies.token import TokenDep, AdminTokenDep
from ..dependencies.database import SessionDep
from ..dependencies.pagination import PaginationDep

from ...db.crud.transaction import TransactionService
from ...schemas.transaction import TransactionRead


router = APIRouter()
tx_service = TransactionService()


@router.get(
    "/me",
    response_model=list[TransactionRead],
    status_code=status.HTTP_200_OK
)
def get_my_transactions(
    token: TokenDep,
    session: SessionDep,
    pagination: PaginationDep
):
    user_id = token.credentials

    tx_s = tx_service.get_transactions_from_user(user_id, session, pagination.limit, pagination.offset)

    return tx_s


@router.get(
    "/all",
    response_model=list[TransactionRead],
    status_code=status.HTTP_200_OK
)
def get_all_transactions(
    token: AdminTokenDep,
    session: SessionDep,
    pagination: PaginationDep
):
    """Get all transactions across all users (admin only)."""
    return tx_service.get_all_transactions(session, pagination.limit, pagination.offset)
