import uuid
from dataclasses import dataclass
from typing import Literal

from sqlmodel import Session, select

from ..models.product import Product
from ..models.transaction import Transaction, TransactionType, ActorType
from ..models.inventory import InventoryMovementReason
from .user import UserService
from .inventory import InventoryService
from ...core.utils import round_money

user_service = UserService()
inventory_service = InventoryService()


@dataclass
class PurchaseResult:
    ok: bool
    reason: Literal["not_found", "inactive", "insufficient_funds"] | None
    new_balance: float | None


class ProductService:

    def create_product(
        self,
        name: str,
        price: float,
        session: Session,
        *,
        inventory_item_id: str | None = None,
    ) -> Product:
        product = Product(
            name=name,
            price=round_money(price),
            inventory_item_id=uuid.UUID(inventory_item_id) if inventory_item_id else None,
        )
        session.add(product)
        session.commit()
        session.refresh(product)
        return product

    def get_all_products(self, session: Session, *, active_only: bool = False) -> list[Product]:
        stmt = select(Product).order_by(Product.name)  # type: ignore
        if active_only:
            stmt = stmt.where(Product.is_active.is_(True))
        return list(session.exec(stmt).all())

    def get_product_by_id(self, product_id: str, session: Session) -> Product | None:
        stmt = select(Product).where(Product.id == uuid.UUID(product_id))
        return session.exec(stmt).first()

    def update_product(
        self,
        product_id: str,
        session: Session,
        *,
        name: str | None = None,
        price: float | None = None,
        is_active: bool | None = None,
        inventory_item_id: str | None = None,
    ) -> Product | None:
        product = self.get_product_by_id(product_id, session)
        if product is None:
            return None

        if name is not None:
            product.name = name
        if price is not None:
            product.price = round_money(price)
        if is_active is not None:
            product.is_active = is_active
        if inventory_item_id is not None:
            product.inventory_item_id = uuid.UUID(inventory_item_id)

        session.add(product)
        session.commit()
        session.refresh(product)
        return product

    def purchase_product(
        self,
        product_id: str,
        user_id: str,
        session: Session,
    ) -> PurchaseResult:
        """Reuses the exact debit pattern already proven in
        print_assistant.py — atomic adjust_balance with the credit limit
        enforced, same as a print job's cost."""
        product = self.get_product_by_id(product_id, session)
        if product is None:
            return PurchaseResult(False, "not_found", None)
        if not product.is_active:
            return PurchaseResult(False, "inactive", None)

        result = user_service.adjust_balance(
            user_id, -product.price, session, enforce_credit_limit=True
        )
        if not result.ok:
            reason = "not_found" if result.reason == "not_found" else "insufficient_funds"
            return PurchaseResult(False, reason, None)

        tx = Transaction(
            user_id=uuid.UUID(user_id),
            type=TransactionType.PRODUCT_PURCHASE,
            amount=-product.price,
            balance_after=result.new_balance,
            actor_id=uuid.UUID(user_id),
            actor_type=ActorType.USER,
            target_user_id=uuid.UUID(user_id),
            related_product_id=product.id,
            note=f"Purchased: {product.name}",
        )
        session.add(tx)
        session.commit()

        if product.inventory_item_id is not None:
            inventory_service.record_movement(
                str(product.inventory_item_id), -1, InventoryMovementReason.PRODUCT_SALE, session,
                related_product_id=str(product.id),
            )

        return PurchaseResult(True, None, result.new_balance)
