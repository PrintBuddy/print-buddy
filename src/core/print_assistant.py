from fastapi import status, HTTPException
from sqlmodel import Session
import uuid

from ..db.crud.user import UserService
from ..db.crud.printer import PrinterService
from ..db.crud.file import FileService
from ..db.crud.printjob import PrintJobService
from ..db.crud.transaction import TransactionService

from ..db.models.transaction import TransactionType

from ..schemas.printjob import PrintJobCreate
from ..schemas.transaction import TransactionCreate

from .cups_manager import cups_manager as cups_mgr

from .logger import logger
from .utils import round_money


user_service = UserService()
printer_service = PrinterService()
file_service = FileService()
pj_service = PrintJobService()
tx_service = TransactionService()

class PrintAssistant:

    def get_file_to_print(
        self,
        user_id: str,
        file_id: str,
        session: Session
    ):
        check = False
        file = file_service.get_file_by_id(
            file_id, session
        )

        if file is not None:
            check = str(file.user_id) == user_id

        if not check or file is None:
            logger.error("File not found or not from user")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found or not from user"
            )
        
        return file
    
    def get_printer(
        self,
        printer_name: str,
        session: Session
    ):
        printer = printer_service.get_printer_by_name(
            printer_name, session
        )

        if printer is None:
            logger.error(f"Printer {printer_name} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Printer not found"
            )
        
        return printer
    
    def send_print_job(
        self,
        printjob: PrintJobCreate,
        session: Session
    ):
        printer_name = printjob.printer.name
        filepath = printjob.file.filepath
        print_options = printjob.print_options

        username = user_service.get_username_by_id(printjob.user_id, session)

        # Reserve funds atomically before sending anything to CUPS, so an
        # unpayable job never reaches the printer. Refunded below if the
        # CUPS send itself then fails.
        debit = user_service.adjust_balance(
            printjob.user_id,
            -printjob.cost,
            session,
            enforce_credit_limit=True,
        )
        if not debit.ok:
            if debit.reason == "not_found":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            logger.error(f"User {printjob.user_id} has insufficient balance to print")
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient balance to print"
            )

        cups_id = cups_mgr.print_file(
            printer_name=printer_name,
            file_path=filepath,
            title=f"{username} job in {printer_name}",
            options=print_options.cups_options
        )

        if not cups_id:
            logger.error(f"Unable to send printjob of file {printjob.file.filename} to CUPS")
            user_service.adjust_balance(
                printjob.user_id,
                printjob.cost,
                session,
                enforce_credit_limit=False,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to send print job to CUPS service"
            )

        # UPDATE TONER LEVELS
        cups_mgr.get_toner_levels(printer_name)

        pj = pj_service.create_job(
            cups_id=cups_id,
            printjob=printjob,
            session=session
        )

        tx_data = TransactionCreate(
            user_id=uuid.UUID(printjob.user_id),
            type=TransactionType.PRINT,
            amount=-round_money(printjob.cost),
            balance_after=debit.new_balance,  # type: ignore
            note=f"Printed file: {pj.file_name}"
        )

        tx_service.create_transaction(tx_data, session)

        return pj
