from fastapi import APIRouter, status, HTTPException
from ..dependencies.database import SessionDep

from ...schemas.telegram import GenerateVoucher, TelegramID, UserBalance
from ...schemas.voucher import VoucherRead
from ...schemas.user import UserRead, UserAdminRead
from ...core.voucher_assistant import VoucherAssistant
from ...db.crud.user import UserService

from ...schemas.transaction import TransactionCreate
from ...db.crud.transaction import TransactionService
from ...db.models.transaction import TransactionType

from ...db.crud.telegram_admin import TelegramAdminService


router = APIRouter()
voucher_assistant = VoucherAssistant()
user_service = UserService()
tx_service = TransactionService()
ta_service = TelegramAdminService()


def _require_telegram_admin(chat_id: str, session) -> str:
    """Return the PrintBuddy user_id (str) for an authorised Telegram chat_id, or raise 403."""
    ta = ta_service.get_telegram_admin(str(chat_id), session)
    if ta is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Telegram ID not allowed"
        )
    return str(ta.user_id)


@router.get(
    "/users",
    status_code=status.HTTP_200_OK,
    response_model=list[UserAdminRead]
)
def get_users(
    telegram_id: TelegramID,
    session: SessionDep
):
    """Return the list of all users for an authorised Telegram admin."""
    _require_telegram_admin(telegram_id.chat_id, session)
    return user_service.get_users(session)


@router.get(
    "/user/{username}",
    status_code=status.HTTP_200_OK,
    response_model=UserRead
)
def get_user(
    username: str,
    telegram_id: TelegramID,
    session: SessionDep
):
    _require_telegram_admin(telegram_id.chat_id, session)
    user = user_service.get_user_by_username(username, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=UserRead
)
def get_me(
    telegram_id: TelegramID,
    session: SessionDep
):
    admin_id = _require_telegram_admin(telegram_id.chat_id, session)
    user = user_service.get_user_by_id(admin_id, session)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post(
    "/generate-voucher",
    status_code=status.HTTP_200_OK,
    response_model=VoucherRead
)
def generate_voucher(
    voucher_data: GenerateVoucher,
    session: SessionDep
):
    admin_id = _require_telegram_admin(voucher_data.chat_id, session)
    voucher = voucher_assistant.generate_voucher(admin_id, voucher_data.amount, session)
    return voucher


@router.patch(
    "/balance-adjust",
    status_code=status.HTTP_200_OK,
    response_model=UserRead
)
def adjust_balance(
    adjust_data: UserBalance,
    session: SessionDep
):
    admin_id = _require_telegram_admin(adjust_data.chat_id, session)

    user = user_service.get_user_by_username(adjust_data.username, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    user_id = str(user.id)
    amount = adjust_data.amount

    balance = user.balance
    diff = amount - balance
    if diff >= 0:
        user_service.add_credit(user_id, diff, session)
    else:
        user_service.discount_credit(user_id, -diff, session)

    balance = user_service.get_user_balance(user_id, session)
    admin = user_service.get_username_by_id(admin_id, session)

    tx_data = TransactionCreate(
        user_id=user.id,
        type=TransactionType.ADJUSTMENT,
        amount=diff,
        balance_after=balance,  # type: ignore
        note=f"Adjusted by {admin}"
    )

    tx_service.create_transaction(tx_data, session)

    return user


@router.patch(
    "/recharge",
    status_code=status.HTTP_200_OK,
)
def recharge_user(
    recharge_info: UserBalance,
    session: SessionDep
):
    admin_id = _require_telegram_admin(recharge_info.chat_id, session)

    user = user_service.get_user_by_username(recharge_info.username, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    user_id = str(user.id)
    amount = recharge_info.amount

    success = user_service.add_credit(user_id, amount, session)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to recharge user"
        )
    
    balance = user_service.get_user_balance(user_id, session)
    admin = user_service.get_username_by_id(admin_id, session)

    tx_data = TransactionCreate(
        user_id=user.id,
        type=TransactionType.RECHARGE,
        amount=amount,
        balance_after=balance,  # type: ignore
        note=f"Recharge made by {admin}"
    )

    tx_service.create_transaction(tx_data, session)
    
    return { "success": True }


@router.post(
    "/add-admin/{username}/{user_telegram_id}",
    status_code=status.HTTP_201_CREATED
)
def add_telegram_admin(
    user_telegram_id: str,
    username: str,
    telegram_id: TelegramID,
    session: SessionDep
):
    ta = ta_service.get_telegram_admin(telegram_id.chat_id, session)
    if ta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    admin_id = ta.user_id

    is_admin = user_service.user_is_admin(str(admin_id), session)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not admin"
        )
    
    user = user_service.get_user_by_username(username, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user_id = user.id

    ta_service.create_telegram_admin(
        str(user_id), user_telegram_id, session
    )

    return { "success": True }