import hmac

from fastapi import APIRouter, Depends, Header, status, HTTPException
from fastapi.responses import JSONResponse

from ..dependencies.database import SessionDep

from ...schemas.telegram import (
    RechargeRequestAction,
    TelegramID,
    TelegramRechargeRequestCreate,
    TelegramRechargeRequestResolve,
    TelegramRechargeRequestResult,
    TelegramProductPurchaseResolve,
    TelegramProductPurchaseResult,
    TelegramStockAdjust,
    TelegramExpenseCreate,
    UserBalance,
)
from ...schemas.user import UserRead, UserAdminRead
from ...schemas.inventory import InventoryItemRead
from ...db.crud.user import UserService

from ...db.models.transaction import ActorType
from ...db.models.inventory import InventoryMovementReason

from ...db.crud.telegram_admin import TelegramAdminService
from ...db.crud.recharge_request import RechargeRequestService
from ...db.crud.product_purchase import ProductPurchaseService
from ...db.crud.inventory import InventoryService
from ...db.crud.expense import ExpenseService
from ...db.models.recharge_request import RechargeRequest
from ...core.utils import round_money
from ...core.config import settings
from ...core.ledger_service import LedgerService
from ...core.recharge_request_service import recharge_request_resolver
from ...core.product_purchase_service import product_purchase_manager


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
ta_service = TelegramAdminService()
recharge_request_service = RechargeRequestService()
purchase_service = ProductPurchaseService()
ledger_service = LedgerService()
inventory_service = InventoryService()
expense_service = ExpenseService()


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
        # Only ever set for requests created from the web app (see
        # api/routes/recharge_request.py) — lets the bot edit that single
        # message in place if a web-created request gets approved/rejected
        # by pressing its Telegram button, even though the bot's own
        # in-memory notification tracking never saw this request created.
        "notified_chat_id": request.notified_chat_id,
        "notified_message_id": request.notified_message_id,
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

    admin = user_service.get_username_by_id(admin_id, session)

    result = ledger_service.record_adjustment(
        user_id, amount, admin_id, ActorType.ADMIN, session,
        note=f"Adjusted by {admin}",
        current_balance=user.balance,
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

    admin = user_service.get_username_by_id(admin_id, session)

    result = ledger_service.record_recharge(
        user_id, amount, admin_id, ActorType.ADMIN, session,
        note=f"Recharge made by {admin}",
        enforce_credit_limit=False,
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

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

    result = recharge_request_resolver.resolve(
        request_id,
        approve=(resolve_data.action == RechargeRequestAction.APPROVE),
        actor_id=admin_id,
        actor_type=ActorType.ADMIN,
        resolved_by_username=admin_username,
        session=session,
    )

    if not result.ok:
        if result.reason == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recharge request not found")
        if result.reason == "already_resolved":
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "detail": "Recharge request has already been resolved",
                    "status": result.request.status.value,
                    "resolved_by_username": result.request.resolved_by_username,
                },
            )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    request = result.request
    user = user_service.get_user_by_id(str(request.user_id), session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {
        "request": _serialize_recharge_request(request),
        "admin_chat_ids": ta_service.get_all_chat_ids(session),
        "user_name": user.name,
        "user_surname": user.surname,
    }


def _serialize_purchase(purchase) -> dict:
    return {
        "id": purchase.id,
        "user_id": purchase.user_id,
        "username": purchase.username,
        "product_name": purchase.product_name,
        "quantity": purchase.quantity,
        "total_amount": round_money(purchase.total_amount),
        "message": purchase.message,
        "status": purchase.status,
        "admin_message": purchase.admin_message,
        "resolved_by_username": purchase.resolved_by_username,
        "created_at": purchase.created_at,
        "updated_at": purchase.updated_at,
    }


@router.patch(
    "/product-purchases/{purchase_id}",
    status_code=status.HTTP_200_OK,
    response_model=TelegramProductPurchaseResult,
)
def resolve_product_purchase(
    purchase_id: str,
    resolve_data: TelegramProductPurchaseResolve,
    session: SessionDep,
):
    """Resolves a purchase pressed from Telegram. Unlike the web route,
    this deliberately does NOT edit any Telegram messages itself — the
    bot process handling the button press already has a live connection
    to edit them directly, and is given every notification's chat_id/
    message_id below to do so, mirroring how the web route (which has no
    bot process to hand this off to) does the editing itself instead."""
    admin_id = _require_telegram_admin(resolve_data.chat_id, session)
    admin_username = user_service.get_username_by_id(admin_id, session)
    if admin_username is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin user not found")

    result = product_purchase_manager.resolve(
        purchase_id,
        resolve_data.action.value,
        admin_id,
        ActorType.ADMIN,
        admin_username,
        session,
    )

    if not result.ok:
        if result.reason == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase not found")
        if result.reason == "already_resolved":
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "detail": "Purchase has already been resolved",
                    "status": result.purchase.status.value,
                    "resolved_by_username": result.purchase.resolved_by_username,
                },
            )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    notifications = purchase_service.get_notifications(str(result.purchase.id), session)

    return {
        "purchase": _serialize_purchase(result.purchase),
        "notifications": [{"chat_id": n.chat_id, "message_id": n.message_id} for n in notifications],
    }


def _serialize_inventory_item(item) -> InventoryItemRead:
    return InventoryItemRead(
        id=item.id,
        name=item.name,
        category=item.category,
        unit=item.unit,
        current_stock=item.current_stock,
        low_stock_threshold=item.low_stock_threshold,
        printer_id=item.printer_id,
        reorder_supplier=item.reorder_supplier,
        is_active=item.is_active,
        is_low_stock=item.current_stock <= item.low_stock_threshold,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get(
    "/inventory",
    status_code=status.HTTP_200_OK,
    response_model=list[InventoryItemRead],
)
def get_inventory(
    telegram_id: TelegramID,
    session: SessionDep,
):
    """Active inventory items, for the bot's /stock item picker."""
    _require_telegram_admin(telegram_id.chat_id, session)
    items = inventory_service.get_all_items(session, active_only=True)
    return [_serialize_inventory_item(item) for item in items]


@router.patch(
    "/stock-adjust",
    status_code=status.HTTP_200_OK,
    response_model=InventoryItemRead,
)
def adjust_stock(
    adjust_data: TelegramStockAdjust,
    session: SessionDep,
):
    """Manual stock correction from Telegram — always MANUAL_ADJUSTMENT,
    same as the web app's Adjust Stock action, just reached by item name
    instead of item id since the bot only has a name to work with."""
    admin_id = _require_telegram_admin(adjust_data.chat_id, session)
    admin_username = user_service.get_username_by_id(admin_id, session)

    item = inventory_service.get_item_by_name(adjust_data.item_name, session)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    result = inventory_service.record_movement(
        str(item.id), adjust_data.delta, InventoryMovementReason.MANUAL_ADJUSTMENT, session,
        notes=f"Adjusted via Telegram by {admin_username}",
    )
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    return _serialize_inventory_item(inventory_service.get_item_by_id(str(item.id), session))


@router.post(
    "/expenses",
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    expense_data: TelegramExpenseCreate,
    session: SessionDep,
):
    """Logs an expense from Telegram. The bot itself is responsible for
    confirming with the admin before calling this — an expense is a
    permanent ledger entry, unlike a stock adjustment. Always attributes
    both recorded_by and paid_by to the calling admin — Telegram has no
    equivalent of the web app's "pick a different payer" picker."""
    admin_id = _require_telegram_admin(expense_data.chat_id, session)

    expense_service.create_expense(
        expense_data.category,
        round_money(expense_data.amount),
        expense_data.description,
        admin_id,
        session,
    )

    return {"success": True}


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
