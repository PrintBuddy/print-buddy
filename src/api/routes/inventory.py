from fastapi import APIRouter, status, HTTPException

from ..dependencies.token import AdminTokenDep
from ..dependencies.database import SessionDep

from ...schemas.inventory import (
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
    InventoryMovementCreate,
    InventoryMovementRead,
    RestockRequest,
)
from ...db.crud.inventory import InventoryService
from ...db.models.inventory import InventoryMovementReason


router = APIRouter()

inventory_service = InventoryService()


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
        is_active=item.is_active,
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
    active_only: bool = False,
):
    return [_to_read(item) for item in inventory_service.get_all_items(session, active_only=active_only)]


@router.patch(
    "/{item_id}",
    response_model=InventoryItemRead,
    status_code=status.HTTP_200_OK,
)
def update_item(
    item_id: str,
    data: InventoryItemUpdate,
    token: AdminTokenDep,
    session: SessionDep,
):
    item = inventory_service.update_item(
        item_id, session,
        name=data.name,
        category=data.category,
        unit=data.unit,
        low_stock_threshold=data.low_stock_threshold,
        printer_id=str(data.printer_id) if data.printer_id else None,
        reorder_supplier=data.reorder_supplier,
        is_active=data.is_active,
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return _to_read(item)


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

    result = inventory_service.record_movement(
        item_id, data.delta, data.reason, session, notes=data.notes,
    )
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
    """Records new stock arriving. Deliberately doesn't touch Expense — the
    purchase is normally logged separately (and days earlier); log it via
    the Log Expense flow if it hasn't been already."""
    item = inventory_service.get_item_by_id(item_id, session)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    result = inventory_service.record_movement(
        item_id, data.quantity, InventoryMovementReason.PURCHASE, session,
    )
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    return _to_read(inventory_service.get_item_by_id(item_id, session))
