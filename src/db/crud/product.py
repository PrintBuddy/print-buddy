import uuid

from sqlmodel import Session, select

from ..models.product import Product
from ...core.utils import round_money


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

    def delete_product(self, product_id: str, session: Session) -> Product | None:
        product = self.get_product_by_id(product_id, session)
        if product is None:
            return None
        session.delete(product)
        session.commit()
        return product

