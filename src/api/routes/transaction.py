from fastapi import APIRouter, status, HTTPException

from ..dependencies.token import TokenDep, AdminTokenDep
from ..dependencies.database import SessionDep

from ...db.crud.transaction import TransactionService
from ...db.models.transaction import TransactionType
from ...schemas.transaction import TransactionRead, TransactionCreate
from ...schemas.settings import VoucherRedeemConfig

from ...db.crud.user import UserService
from ...db.crud.app_config import AppConfigService


router = APIRouter()
tx_service = TransactionService()
user_service = UserService()
config_service = AppConfigService()
VOUCHER_REDEEM_KEY = "voucher_redeem_config"
VOUCHER_REDEEM_DEFAULT = {"enabled": True}


@router.get(
    "/me",
    response_model=list[TransactionRead],
    status_code=status.HTTP_200_OK
)
def get_my_transactions(
    token: TokenDep,
    session: SessionDep
):
    user_id = token.credentials

    tx_s = tx_service.get_transactions_from_user(user_id, session)

    return tx_s


@router.get(
    "/recharge-info",
    status_code=status.HTTP_200_OK
)
def get_recharge_info(
    token: TokenDep,
    session: SessionDep
):
    data = config_service.get("recharge_info", session)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recharge info not found")
    return data


@router.get(
    "/voucher-redeem",
    response_model=VoucherRedeemConfig,
    status_code=status.HTTP_200_OK
)
def get_voucher_redeem_config(
    token: TokenDep,
    session: SessionDep
):
    data = config_service.get(VOUCHER_REDEEM_KEY, session)
    return data or VOUCHER_REDEEM_DEFAULT


@router.get(
    "/all",
    response_model=list[TransactionRead],
    status_code=status.HTTP_200_OK
)
def get_all_transactions(
    token: AdminTokenDep,
    session: SessionDep
):
    """Get all transactions across all users (admin only)."""
    return tx_service.get_all_transactions(session)
