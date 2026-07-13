import hmac
import uuid

from fastapi import APIRouter, Depends, Header, status, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import select

from ..dependencies.database import SessionDep

from ...schemas.telegram import (
    RechargeRequestAction,
    TelegramID,
    TelegramRechargeRequestCreate,
    TelegramRechargeRequestResolve,
    TelegramRechargeRequestResult,
    UserBalance,
)
from ...schemas.user import UserRead, UserAdminRead
from ...db.crud.user import UserService

from ...schemas.transaction import TransactionCreate
from ...db.crud.transaction import TransactionService
from ...db.models.transaction import Transaction, TransactionType

from ...db.crud.telegram_admin import TelegramAdminService
from ...db.crud.recharge_request import RechargeRequestService
from ...db.models.recharge_request import RechargeRequest, RechargeRequestStatus
from ...core.utils import round_money
from ...core.config import settings


def verify_telegram_secret(x_telegram_secret: str | None = Header(default=None)) -> None:
    """
    Router-level gate: every route below acts on behalf of the bot, so every
    request must carry the shared secret the bot and backend both hold —
    without this, `_require_telegram_admin` only checks a client-supplied
    chat_id, which anyone reaching this API directly could forge.
    """
    if not x_telegram_secret or not hmac.compare_digest(x_telegram_secret, settings.TELEGRAM_SECRET):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid Telegram secret"
        )


router = APIRouter(dependencies=[Depends(verify_telegram_secret)])
user_service = UserService()
tx_service = TransactionService()
ta_service = TelegramAdminService()
recharge_request_service = RechargeRequestService()


def _require_telegram_admin(chat_id: str, session) -> str:
    """Return the PrintBuddy user_id (str) for an authorised Telegram chat_id, or raise 403."""
    ta = ta_service.get_telegram_admin(str(chat_id), session)
    if ta is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Telegram ID not allowed"
        )
    return str(ta.user_id)


def _serialize_recharge_request(request: RechargeRequest) -> dict:
    return {
        "id": request.id,
        "user_id": request.user_id,
        "username": request.username,
        "amount": round_money(request.amount),
        "message": request.message,
        "status": request.status,
        "requester_chat_id": request.requester_chat_id,
        "requester_telegram_username": request.requester_telegram_username,
        "requester_first_name": request.requester_first_name,
        "requester_last_name": request.requester_last_name,
        "resolved_by_username": request.resolved_by_username,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
    }


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
    amount = round_money(adjust_data.amount)

    balance = round_money(user.balance)
    diff = round_money(amount - balance)

    result = user_service.adjust_balance(
        user_id, diff, session, enforce_credit_limit=True
    )
    if not result.ok:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND if result.reason == "not_found"
                else status.HTTP_409_CONFLICT
            ),
            detail=(
                "User not found" if result.reason == "not_found"
                else "Adjustment would exceed the user's credit limit"
            ),
        )

    admin = user_service.get_username_by_id(admin_id, session)

    tx_data = TransactionCreate(
        user_id=user.id,
        type=TransactionType.ADJUSTMENT,
        amount=diff,
        balance_after=result.new_balance,  # type: ignore
        note=f"Adjusted by {admin}"
    )

    tx_service.create_transaction(tx_data, session)

    # `user` was loaded before the atomic update above; its in-memory
    # balance is stale, and this response serializes it.
    user.balance = result.new_balance  # type: ignore
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
    amount = round_money(recharge_info.amount)

    result = user_service.adjust_balance(
        user_id, amount, session, enforce_credit_limit=False
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    admin = user_service.get_username_by_id(admin_id, session)

    tx_data = TransactionCreate(
        user_id=user.id,
        type=TransactionType.RECHARGE,
        amount=amount,
        balance_after=result.new_balance,  # type: ignore
        note=f"Recharge made by {admin}"
    )

    tx_service.create_transaction(tx_data, session)
    
    return { "success": True }


@router.post(
    "/recharge-requests",
    status_code=status.HTTP_201_CREATED,
    response_model=TelegramRechargeRequestResult
)
def create_recharge_request(
    request_data: TelegramRechargeRequestCreate,
    session: SessionDep
):
    amount = round_money(request_data.amount)
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be a positive number")

    if request_data.message is not None:
        request_data.message = request_data.message.strip() or None

    user = user_service.get_user_by_username(request_data.username, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    admin_chat_ids = ta_service.get_all_chat_ids(session)
    if not admin_chat_ids:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No Telegram admins configured")

    request_data.amount = amount
    request = recharge_request_service.create_recharge_request(str(user.id), request_data, session)

    return {
        "request": _serialize_recharge_request(request),
        "admin_chat_ids": admin_chat_ids,
        "user_name": user.name,
        "user_surname": user.surname,
    }


@router.patch(
    "/recharge-requests/{request_id}",
    status_code=status.HTTP_200_OK,
    response_model=TelegramRechargeRequestResult
)
def resolve_recharge_request(
    request_id: str,
    resolve_data: TelegramRechargeRequestResolve,
    session: SessionDep
):
    admin_id = _require_telegram_admin(resolve_data.chat_id, session)
    admin_username = user_service.get_username_by_id(admin_id, session)
    if admin_username is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin user not found")

    stmt = (
        select(RechargeRequest)
        .where(RechargeRequest.id == uuid.UUID(request_id))
        .with_for_update()
    )
    request = session.exec(stmt).first()
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recharge request not found")

    user = user_service.get_user_by_id(str(request.user_id), session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if request.status != RechargeRequestStatus.PENDING:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Recharge request has already been resolved",
                "status": request.status.value,
                "resolved_by_username": request.resolved_by_username,
            },
        )

    if resolve_data.action == RechargeRequestAction.APPROVE:
        result = user_service.adjust_balance(
            str(user.id), request.amount, session, enforce_credit_limit=False
        )
        if not result.ok:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        tx_data = TransactionCreate(
            user_id=user.id,
            type=TransactionType.RECHARGE,
            amount=request.amount,
            balance_after=result.new_balance,
            note=f"Recharge request approved by {admin_username}"
        )
        session.add(Transaction(**tx_data.model_dump()))
        request.status = RechargeRequestStatus.APPROVED
    else:
        request.status = RechargeRequestStatus.REJECTED

    request.resolved_by_username = admin_username
    session.add(request)
    session.commit()
    session.refresh(request)

    return {
        "request": _serialize_recharge_request(request),
        "admin_chat_ids": ta_service.get_all_chat_ids(session),
        "user_name": user.name,
        "user_surname": user.surname,
    }


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
