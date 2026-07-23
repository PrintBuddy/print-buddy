import uuid
from dataclasses import dataclass

from sqlmodel import Session, select
from sqlalchemy import update, func

from ..models.inventory import InventoryItem, InventoryMovement, InventoryCategory, InventoryMovementReason
from ...core.utils import round_money


@dataclass
class StockUpdateResult:
    ok: bool
    new_stock: float | None


class InventoryService:

    def create_item(
        self,
        name: str,
        category: InventoryCategory,
        unit: str,
        low_stock_threshold: float,
        session: Session,
        *,
        initial_stock: float = 0.0,
        printer_id: str | None = None,
        reorder_supplier: str | None = None,
    ) -> InventoryItem:
        item = InventoryItem(
            name=name,
            category=category,
            unit=unit,
            current_stock=round_money(initial_stock),
            low_stock_threshold=round_money(low_stock_threshold),
            printer_id=uuid.UUID(printer_id) if printer_id else None,
            reorder_supplier=reorder_supplier,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return item

    def get_all_items(self, session: Session, *, active_only: bool = False) -> list[InventoryItem]:
        stmt = select(InventoryItem).order_by(InventoryItem.name)  # type: ignore
        if active_only:
            stmt = stmt.where(InventoryItem.is_active.is_(True))
        return list(session.exec(stmt).all())

    def get_item_by_id(self, item_id: str, session: Session) -> InventoryItem | None:
        stmt = select(InventoryItem).where(InventoryItem.id == uuid.UUID(item_id))
        return session.exec(stmt).first()

    def get_item_by_name(self, name: str, session: Session) -> InventoryItem | None:
        stmt = select(InventoryItem).where(func.lower(InventoryItem.name) == name.strip().lower())
        return session.exec(stmt).first()

    def update_item(
        self,
        item_id: str,
        session: Session,
        *,
        name: str | None = None,
        category: InventoryCategory | None = None,
        unit: str | None = None,
        low_stock_threshold: float | None = None,
        printer_id: str | None = None,
        reorder_supplier: str | None = None,
        is_active: bool | None = None,
    ) -> InventoryItem | None:
        item = self.get_item_by_id(item_id, session)
        if item is None:
            return None

        if name is not None:
            item.name = name
        if category is not None:
            item.category = category
        if unit is not None:
            item.unit = unit
        if low_stock_threshold is not None:
            item.low_stock_threshold = round_money(low_stock_threshold)
        if printer_id is not None:
            item.printer_id = uuid.UUID(printer_id)
        if reorder_supplier is not None:
            item.reorder_supplier = reorder_supplier
        if is_active is not None:
            item.is_active = is_active

        session.add(item)
        session.commit()
        session.refresh(item)
        return item

    def get_low_stock_items(self, session: Session) -> list[InventoryItem]:
        stmt = select(InventoryItem).where(InventoryItem.current_stock <= InventoryItem.low_stock_threshold)
        return list(session.exec(stmt).all())

    def record_movement(
        self,
        item_id: str,
        delta: float,
        reason: InventoryMovementReason,
        session: Session,
        *,
        related_job_id: str | None = None,
        related_expense_id: str | None = None,
        related_product_id: str | None = None,
        notes: str | None = None,
    ) -> StockUpdateResult:
        """Atomically applies `delta` to an item's stock (same
        UPDATE...RETURNING pattern as UserService.adjust_balance, so
        concurrent movements against the same item serialize at the DB
        level) and records the movement."""
        delta = round_money(delta)
        item_uuid = uuid.UUID(item_id)

        stmt = (
            update(InventoryItem)
            .where(InventoryItem.id == item_uuid)
            .values(current_stock=InventoryItem.current_stock + delta)
            .returning(InventoryItem.current_stock)
        )
        row = session.execute(stmt).first()
        if row is None:
            session.rollback()
            return StockUpdateResult(False, None)

        movement = InventoryMovement(
            item_id=item_uuid,
            delta=delta,
            reason=reason,
            notes=notes,
            related_job_id=uuid.UUID(related_job_id) if related_job_id else None,
            related_expense_id=uuid.UUID(related_expense_id) if related_expense_id else None,
            related_product_id=uuid.UUID(related_product_id) if related_product_id else None,
        )
        session.add(movement)
        session.commit()

        return StockUpdateResult(True, round_money(row[0]))

    def get_movements_for_item(
        self,
        item_id: str,
        session: Session,
        limit: int = 50,
        offset: int = 0,
    ) -> list[InventoryMovement]:
        stmt = (
            select(InventoryMovement)
            .where(InventoryMovement.item_id == uuid.UUID(item_id))
            .order_by(InventoryMovement.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(stmt).all())
