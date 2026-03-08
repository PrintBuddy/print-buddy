from fastapi import APIRouter, status, HTTPException

from ..dependencies.database import SessionDep
from ..dependencies.token import TokenDep, AdminTokenDep
from ...db.crud.printer import PrinterService
from ...db.crud.user import UserService
from ...schemas.printer import PrinterRead, PrinterCreate, PrinterAdminUpdate, TonerMarker
from ...core.cups_manager import CUPSManager


printer_service = PrinterService()
user_service = UserService()
cups_manager = CUPSManager()

router = APIRouter()


@router.get(
    "",
    response_model=list[PrinterRead],
    status_code=status.HTTP_200_OK
)
def get_printers(
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
    status_code=status.HTTP_201_CREATED
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
    
    return printer
