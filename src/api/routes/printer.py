from fastapi import APIRouter, status, HTTPException
import uuid

from ..dependencies.database import SessionDep
from ..dependencies.token import TokenDep, AdminTokenDep
from ...db.crud.printer import PrinterService
from ...db.crud.group import GroupService
from ...schemas.printer import PrinterRead, PrinterCreate, PrinterAdminUpdate, TonerMarker
from ...core.cups_manager import cups_manager


printer_service = PrinterService()
group_service = GroupService()

router = APIRouter()


@router.get(
    "",
    response_model=list[PrinterRead],
    status_code=status.HTTP_200_OK
)
def get_printers(
    token: TokenDep,
    session: SessionDep
):
    user_id = uuid.UUID(token.credentials)
    printers = group_service.get_accessible_printers(user_id, session)

    result = []
    for printer in printers:
        effective_bw, effective_color = group_service.get_effective_prices(user_id, printer.id, session)
        data = printer.model_dump()
        if effective_bw is not None:
            data["price_per_page_bw"] = effective_bw
        if effective_color is not None:
            data["price_per_page_color"] = effective_color
        result.append(data)

    return result


@router.get(
    "/all",
    response_model=list[PrinterRead],
    status_code=status.HTTP_200_OK
)
def get_all_printers(
    token: AdminTokenDep,
    session: SessionDep
):
    printers = printer_service.get_all_printers(session)
    return printers


@router.post(
    "",
    response_model=PrinterRead,
    status_code=status.HTTP_201_CREATED
)
def create_printer(
    printer_data: PrinterCreate,
    token: AdminTokenDep,
    session: SessionDep
):
    new_printer = printer_service.create_printer(printer_data, session)
    return new_printer


@router.get(
    '/{name}/toner',
    response_model=list[TonerMarker],
    status_code=status.HTTP_200_OK
)
def get_printer_toner(
    name: str,
    token: AdminTokenDep,
    session: SessionDep
):
    printer = printer_service.get_printer_by_name(name, session)
    if printer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Printer not found'
        )

    markers = cups_manager.get_toner_levels(name)
    if markers is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='CUPS is unavailable'
        )

    return markers


@router.get(
    '/{name}',
    response_model=PrinterRead,
    status_code=status.HTTP_200_OK
)
def get_printer_by_name(
    name: str,
    token: TokenDep,
    session: SessionDep
):

    printer = printer_service.get_printer_by_name(name, session)
    if printer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Printer not found'
        )
    
    return printer


@router.patch(
    '/{name}',
    response_model=PrinterRead,
    status_code=status.HTTP_200_OK
)
def update_printer(
    name: str,
    printer_data: PrinterAdminUpdate,
    token: AdminTokenDep,
    session: SessionDep
):
    printer = printer_service.update_printer_admin(name, printer_data, session)
    if printer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Printer not found'
        )
    
    return printer


@router.delete(
    '/{name}',
    response_model=PrinterRead,
    status_code=status.HTTP_200_OK
)
def delete_printer(
    name: str,
    token: AdminTokenDep,
    session: SessionDep
):
    
    printer = printer_service.delete_printer(name, session)
    if printer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Printer not found"
        )

    # Delete marker cache data for this printer
    cups_manager._marker_cache.delete_all(name)

    return printer
