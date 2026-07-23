import uuid

from sqlmodel import Session, select

from ..models.product_purchase import ProductPurchase, ProductPurchaseStatus, ProductPurchaseNotification


class ProductPurchaseService:

    def create(
        self,
        user_id: str,
        username: str,
        product_id: str,
        product_name: str,
        quantity: int,
        unit_price: float,
        total_amount: float,
        message: str | None,
        session: Session,
    ) -> ProductPurchase:
        purchase = ProductPurchase(
            user_id=uuid.UUID(user_id),
            username=username,
            product_id=uuid.UUID(product_id),
            product_name=product_name,
            quantity=quantity,
            unit_price=unit_price,
            total_amount=total_amount,
            message=message,
        )
        session.add(purchase)
        session.commit()
        session.refresh(purchase)
        return purchase

    def get_purchase_by_id(self, purchase_id: str, session: Session) -> ProductPurchase | None:
        stmt = select(ProductPurchase).where(ProductPurchase.id == uuid.UUID(purchase_id))
        return session.exec(stmt).first()

    def get_for_resolve(self, purchase_id: str, session: Session) -> ProductPurchase | None:
        """Row-locked fetch so a web resolve and a Telegram button press on
        the same purchase serialize instead of racing."""
        stmt = (
            select(ProductPurchase)
            .where(ProductPurchase.id == uuid.UUID(purchase_id))
            .with_for_update()
        )
        return session.exec(stmt).first()

    def get_by_user(
        self, user_id: str, session: Session, limit: int = 50, offset: int = 0
    ) -> list[ProductPurchase]:
        stmt = (
            select(ProductPurchase)
            .where(ProductPurchase.user_id == uuid.UUID(user_id))
            .order_by(ProductPurchase.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(stmt).all())

    def get_pending(
        self, session: Session, limit: int = 50, offset: int = 0
    ) -> list[ProductPurchase]:
        stmt = (
            select(ProductPurchase)
            .where(ProductPurchase.status == ProductPurchaseStatus.PENDING)
            .order_by(ProductPurchase.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(stmt).all())

    def get_all(
        self, session: Session, limit: int = 50, offset: int = 0
    ) -> list[ProductPurchase]:
        stmt = (
            select(ProductPurchase)
            .order_by(ProductPurchase.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(stmt).all())

    def add_notification(self, purchase_id: str, chat_id: str, message_id: int, session: Session) -> None:
        session.add(ProductPurchaseNotification(
            purchase_id=uuid.UUID(purchase_id), chat_id=chat_id, message_id=message_id,
        ))
        session.commit()

    def get_notifications(self, purchase_id: str, session: Session) -> list[ProductPurchaseNotification]:
        stmt = select(ProductPurchaseNotification).where(
            ProductPurchaseNotification.purchase_id == uuid.UUID(purchase_id)
        )
        return list(session.exec(stmt).all())
