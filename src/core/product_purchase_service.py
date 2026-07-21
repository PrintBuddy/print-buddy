import uuid
from dataclasses import dataclass
from typing import Literal

from sqlmodel import Session

from ..db.crud.product import ProductService
from ..db.crud.product_purchase import ProductPurchaseService as ProductPurchaseCrud
from ..db.crud.user import UserService
from ..db.crud.inventory import InventoryService
from ..db.models.product_purchase import ProductPurchase, ProductPurchaseStatus
from ..db.models.transaction import Transaction, TransactionType, ActorType
from ..db.models.inventory import InventoryMovementReason
from .utils import round_money

product_service = ProductService()
purchase_crud = ProductPurchaseCrud()
user_service = UserService()
inventory_service = InventoryService()


@dataclass
class CreatePurchaseResult:
    ok: bool
    reason: Literal["not_found", "inactive", "insufficient_funds"] | None
    purchase: ProductPurchase | None


@dataclass
class ResolvePurchaseResult:
    ok: bool
    reason: Literal["not_found", "already_resolved", "user_not_found"] | None
    purchase: ProductPurchase | None


class ProductPurchaseManager:
    """Buying an extra debits the user immediately (same atomic pattern as
    a print job) but stays PENDING until an admin resolves it — FULFILLED
    once it's actually handed over, or REJECTED with an automatic refund
    if it isn't. This is what stops a stray tap from silently completing
    a purchase with no way back."""

    def create_purchase(
        self,
        product_id: str,
        user_id: str,
        username: str,
        quantity: int,
        message: str | None,
        session: Session,
    ) -> CreatePurchaseResult:
        product = product_service.get_product_by_id(product_id, session)
        if product is None:
            return CreatePurchaseResult(False, "not_found", None)
        if not product.is_active:
            return CreatePurchaseResult(False, "inactive", None)

        total = round_money(product.price * quantity)

        result = user_service.adjust_balance(user_id, -total, session, enforce_credit_limit=True)
        if not result.ok:
            reason = "not_found" if result.reason == "not_found" else "insufficient_funds"
            return CreatePurchaseResult(False, reason, None)

        purchase = purchase_crud.create(
            user_id, username, str(product.id), product.name, quantity,
            product.price, total, message, session,
        )

        tx = Transaction(
            user_id=uuid.UUID(user_id), type=TransactionType.PRODUCT_PURCHASE, amount=-total,
            balance_after=result.new_balance, actor_id=uuid.UUID(user_id), actor_type=ActorType.USER,
            target_user_id=uuid.UUID(user_id), related_product_id=product.id,
            related_product_purchase_id=purchase.id,
            note=f"Purchased {quantity}x {product.name}",
        )
        session.add(tx)
        session.commit()

        return CreatePurchaseResult(True, None, purchase)

    def resolve(
        self,
        purchase_id: str,
        action: Literal["fulfill", "reject"],
        actor_id: str,
        actor_type: ActorType,
        resolved_by_username: str,
        session: Session,
        admin_message: str | None = None,
    ) -> ResolvePurchaseResult:
        purchase = purchase_crud.get_for_resolve(purchase_id, session)
        if purchase is None:
            return ResolvePurchaseResult(False, "not_found", None)
        if purchase.status != ProductPurchaseStatus.PENDING:
            return ResolvePurchaseResult(False, "already_resolved", purchase)

        if action == "fulfill":
            product = (
                product_service.get_product_by_id(str(purchase.product_id), session)
                if purchase.product_id else None
            )
            if product is not None and product.inventory_item_id is not None:
                inventory_service.record_movement(
                    str(product.inventory_item_id), -purchase.quantity, InventoryMovementReason.PRODUCT_SALE,
                    session, related_product_id=str(product.id),
                )
            purchase.status = ProductPurchaseStatus.FULFILLED
        else:
            result = user_service.adjust_balance(
                str(purchase.user_id), purchase.total_amount, session, enforce_credit_limit=False
            )
            if not result.ok:
                return ResolvePurchaseResult(False, "user_not_found", purchase)

            tx = Transaction(
                user_id=purchase.user_id, type=TransactionType.REFUND, amount=purchase.total_amount,
                balance_after=result.new_balance, actor_id=uuid.UUID(actor_id), actor_type=actor_type,
                target_user_id=purchase.user_id, related_product_purchase_id=purchase.id,
                note=admin_message or f"Purchase rejected by {resolved_by_username}",
            )
            session.add(tx)
            purchase.status = ProductPurchaseStatus.REJECTED

        purchase.admin_message = admin_message
        purchase.resolved_by_username = resolved_by_username
        session.add(purchase)
        session.commit()
        session.refresh(purchase)

        return ResolvePurchaseResult(True, None, purchase)


product_purchase_manager = ProductPurchaseManager()
