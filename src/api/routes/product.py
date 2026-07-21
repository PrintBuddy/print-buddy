from fastapi import APIRouter, status, HTTPException

from ..dependencies.token import TokenDep, AdminTokenDep
from ..dependencies.database import SessionDep
from ..dependencies.pagination import PaginationDep

from ...schemas.product import ProductCreate, ProductUpdate, ProductRead
from ...schemas.product_purchase import ProductPurchaseCreate, ProductPurchaseResolve, ProductPurchaseRead, ProductPurchaseAdminRead
from ...db.crud.product import ProductService
from ...db.crud.product_purchase import ProductPurchaseService
from ...db.crud.telegram_admin import TelegramAdminService
from ...db.crud.user import UserService
from ...db.models.transaction import ActorType
from ...core.product_purchase_service import product_purchase_manager
from ...core.telegram_notifier import telegram_notifier


router = APIRouter()

product_service = ProductService()
purchase_service = ProductPurchaseService()
ta_service = TelegramAdminService()
user_service = UserService()


def _purchase_notification_text(user, purchase) -> str:
    lines = [
        "🛍️ <b>New Extras Purchase</b>",
        "",
        f"👤 <b>User:</b> {user.name} {user.surname} (@{user.username})",
        f"📦 <b>Item:</b> {purchase.quantity}x {purchase.product_name}",
        f"💶 <b>Total:</b> {purchase.total_amount:.2f}€",
    ]
    if purchase.message:
        lines.append(f"📝 <b>Message:</b> {purchase.message}")
    return "\n".join(lines)


def _purchase_resolution_text(purchase, resolved_by: str) -> str:
    fulfilled = purchase.status.value == "fulfilled"
    header = "✅ <b>Purchase Given</b>" if fulfilled else "❌ <b>Purchase Rejected & Refunded</b>"
    text = (
        f"{header}\n\n"
        f"👤 <b>User:</b> {purchase.username}\n"
        f"📦 <b>Item:</b> {purchase.quantity}x {purchase.product_name}\n"
        f"💶 <b>Total:</b> {purchase.total_amount:.2f}€\n"
        f"🛠️ <b>Handled by:</b> {resolved_by}"
    )
    if purchase.admin_message:
        text += f"\n📝 <b>Note:</b> {purchase.admin_message}"
    return text


def _broadcast_new_purchase(user, purchase, session):
    admin_pairs = ta_service.get_eligible_admins(session)
    text = _purchase_notification_text(user, purchase)
    for telegram_admin, _admin_user in admin_pairs:
        message_id = telegram_notifier.send_product_purchase_message(
            telegram_admin.telegram_id, text, str(purchase.id)
        )
        if message_id is not None:
            purchase_service.add_notification(str(purchase.id), telegram_admin.telegram_id, message_id, session)


def _sync_notifications(purchase, resolved_by: str, session):
    text = _purchase_resolution_text(purchase, resolved_by)
    for notification in purchase_service.get_notifications(str(purchase.id), session):
        telegram_notifier.edit_message(notification.chat_id, notification.message_id, text)


@router.get(
    "",
    response_model=list[ProductRead],
    status_code=status.HTTP_200_OK,
)
def get_products(
    token: TokenDep,
    session: SessionDep,
):
    """The "Extras" store — active products only for regular users."""
    return product_service.get_all_products(session, active_only=True)


@router.post(
    "/{product_id}/purchase",
    response_model=ProductPurchaseRead,
    status_code=status.HTTP_201_CREATED,
)
def purchase_product(
    product_id: str,
    data: ProductPurchaseCreate,
    token: TokenDep,
    session: SessionDep,
):
    user_id = token.credentials
    user = user_service.get_user_by_id(user_id, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = product_purchase_manager.create_purchase(
        product_id, user_id, user.username, data.quantity, data.message, session
    )

    if not result.ok:
        if result.reason == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        if result.reason == "inactive":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This product is no longer available")
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient balance")

    _broadcast_new_purchase(user, result.purchase, session)

    return result.purchase


@router.get(
    "/purchases/me",
    response_model=list[ProductPurchaseRead],
    status_code=status.HTTP_200_OK,
)
def get_my_purchases(
    token: TokenDep,
    session: SessionDep,
    pagination: PaginationDep,
):
    user_id = token.credentials
    return purchase_service.get_by_user(user_id, session, pagination.limit, pagination.offset)


@router.get(
    "/purchases/pending",
    response_model=list[ProductPurchaseAdminRead],
    status_code=status.HTTP_200_OK,
)
def get_pending_purchases(
    token: AdminTokenDep,
    session: SessionDep,
    pagination: PaginationDep,
):
    return purchase_service.get_pending(session, pagination.limit, pagination.offset)


@router.get(
    "/purchases",
    response_model=list[ProductPurchaseAdminRead],
    status_code=status.HTTP_200_OK,
)
def get_all_purchases(
    token: AdminTokenDep,
    session: SessionDep,
    pagination: PaginationDep,
):
    """Full history, any status — for the admin Requests view."""
    return purchase_service.get_all(session, pagination.limit, pagination.offset)


@router.patch(
    "/purchases/{purchase_id}",
    response_model=ProductPurchaseAdminRead,
    status_code=status.HTTP_200_OK,
)
def resolve_purchase(
    purchase_id: str,
    data: ProductPurchaseResolve,
    token: AdminTokenDep,
    session: SessionDep,
):
    admin_id = token.credentials
    admin_username = user_service.get_username_by_id(admin_id, session)
    if admin_username is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin user not found")

    result = product_purchase_manager.resolve(
        purchase_id, data.action, admin_id, ActorType.ADMIN, admin_username, session,
        admin_message=data.admin_message,
    )

    if not result.ok:
        if result.reason == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase not found")
        if result.reason == "already_resolved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Already resolved by {result.purchase.resolved_by_username}"
                if result.purchase and result.purchase.resolved_by_username
                else "This purchase has already been resolved",
            )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    _sync_notifications(result.purchase, admin_username, session)

    return result.purchase


# ─── Admin ────────────────────────────────────────────────────────────────────

@router.get(
    "/admin",
    response_model=list[ProductRead],
    status_code=status.HTTP_200_OK,
)
def get_all_products_admin(
    token: AdminTokenDep,
    session: SessionDep,
):
    """Every product, including inactive ones — for management."""
    return product_service.get_all_products(session, active_only=False)


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    data: ProductCreate,
    token: AdminTokenDep,
    session: SessionDep,
):
    return product_service.create_product(
        data.name, data.price, session,
        inventory_item_id=str(data.inventory_item_id) if data.inventory_item_id else None,
    )


@router.patch(
    "/{product_id}",
    response_model=ProductRead,
    status_code=status.HTTP_200_OK,
)
def update_product(
    product_id: str,
    data: ProductUpdate,
    token: AdminTokenDep,
    session: SessionDep,
):
    product = product_service.update_product(
        product_id, session,
        name=data.name,
        price=data.price,
        is_active=data.is_active,
        inventory_item_id=str(data.inventory_item_id) if data.inventory_item_id else None,
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_200_OK,
)
def delete_product(
    product_id: str,
    token: AdminTokenDep,
    session: SessionDep,
):
    product = product_service.delete_product(product_id, session)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return {"success": True}
