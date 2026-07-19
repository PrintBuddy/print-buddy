from fastapi import APIRouter, status, HTTPException

from ..dependencies.token import AdminTokenDep
from ..dependencies.database import SessionDep

from ...schemas.inventory import (
    InventoryItemCreate,
    InventoryItemRead,
    InventoryMovementCreate,
    InventoryMovementRead,
    RestockRequest,
)
from ...db.crud.inventory import InventoryService
from ...db.crud.expense import ExpenseService
from ...db.models.inventory import InventoryMovementReason


router = APIRouter()

inventory_service = InventoryService()
expense_service = ExpenseService()


def _to_read(item) -> InventoryItemRead:
    return InventoryItemRead(
        id=item.id,
        name=item.name,
        category=item.category,
        unit=item.unit,
        current_stock=item.current_stock,
        low_stock_threshold=item.low_stock_threshold,
        printer_id=item.printer_id,
        reorder_supplier=item.reorder_supplier,
        is_low_stock=item.current_stock <= item.low_stock_threshold,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post(
    "",
    response_model=InventoryItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_item(
    data: InventoryItemCreate,
    token: AdminTokenDep,
    session: SessionDep,
):
    item = inventory_service.create_item(
        data.name, data.category, data.unit, data.low_stock_threshold, session,
        initial_stock=data.initial_stock,
        printer_id=str(data.printer_id) if data.printer_id else None,
        reorder_supplier=data.reorder_supplier,
    )
    return _to_read(item)


@router.get(
    "",
    response_model=list[InventoryItemRead],
    status_code=status.HTTP_200_OK,
)
def get_all_items(
    token: AdminTokenDep,
    session: SessionDep,
):
    return [_to_read(item) for item in inventory_service.get_all_items(session)]


@router.get(
    "/{item_id}/movements",
    response_model=list[InventoryMovementRead],
    status_code=status.HTTP_200_OK,
)
def get_item_movements(
    item_id: str,
    token: AdminTokenDep,
    session: SessionDep,
):
    item = inventory_service.get_item_by_id(item_id, session)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return inventory_service.get_movements_for_item(item_id, session)


@router.post(
    "/{item_id}/adjust",
    response_model=InventoryItemRead,
    status_code=status.HTTP_200_OK,
)
def adjust_stock(
    item_id: str,
    data: InventoryMovementCreate,
    token: AdminTokenDep,
    session: SessionDep,
):
    """Manual correction (e.g. a stock count found a discrepancy) — not
    tied to a purchase or a print job."""
    item = inventory_service.get_item_by_id(item_id, session)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    result = inventory_service.record_movement(item_id, data.delta, data.reason, session)
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    return _to_read(inventory_service.get_item_by_id(item_id, session))


@router.post(
    "/{item_id}/restock",
    response_model=InventoryItemRead,
    status_code=status.HTTP_200_OK,
)
def restock_item(
    item_id: str,
    data: RestockRequest,
    token: AdminTokenDep,
    session: SessionDep,
):
    """Logs the purchase as an Expense and records the stock increase in
    one submit, so restocking never leaves the two disconnected."""
    admin_id = token.credentials
    item = inventory_service.get_item_by_id(item_id, session)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    expense = expense_service.create_expense(
        data.expense_category, data.expense_amount, data.expense_description, admin_id, session,
    )

    result = inventory_service.record_movement(
        item_id, data.quantity, InventoryMovementReason.PURCHASE, session,
        related_expense_id=str(expense.id),
    )
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    return _to_read(inventory_service.get_item_by_id(item_id, session))
