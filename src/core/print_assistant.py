from fastapi import status, HTTPException
from sqlmodel import Session
import uuid

from ..db.crud.user import UserService
from ..db.crud.printer import PrinterService
from ..db.crud.file import FileService
from ..db.crud.printjob import PrintJobService
from ..db.crud.transaction import TransactionService

from ..db.models.transaction import TransactionType, ActorType

from ..schemas.printjob import PrintJobCreate
from ..schemas.transaction import TransactionCreate
from ..schemas.print import PrintOptions, SidesOption
from ..db.models.printerjob import PrintJob

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
            note=f"Printed file: {pj.file_name}",
            actor_id=uuid.UUID(printjob.user_id),
            actor_type=ActorType.USER,
            target_user_id=uuid.UUID(printjob.user_id),
            related_job_id=pj.id,
        )

        tx_service.create_transaction(tx_data, session)

        return pj

    def send_free_reprint(
        self,
        original_job: PrintJob,
        admin_id: str,
        reason: str,
        session: Session,
    ) -> PrintJob:
        """Re-submits an earlier job at no cost. Deliberately doesn't
        reuse send_print_job: that method always debits the printing
        user and attributes the resulting Transaction to them as actor,
        which would misrepresent who authorized this (the admin, not the
        user) even though the amount is 0. No debit, no reversal-on-
        failure needed here since nothing is ever charged.

        Only reconstructs what a PrintJob row actually stores — number_up,
        two_sided, color — not the original copies/page-range, which
        aren't persisted per-job; reprints the whole file, once.
        """
        file = file_service.get_file_by_id(str(original_job.file_id), session) if original_job.file_id else None
        if file is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The original file is no longer available to reprint"
            )

        printer = printer_service.get_printer_by_id(original_job.printer_id, session)
        if printer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Printer not found")

        print_options = PrintOptions(
            copies=1,
            sides=SidesOption.TWO_SIDED_LONG if original_job.two_sided else SidesOption.ONE_SIDED,
            color=original_job.color,
            page_ranges="all",
            number_up=original_job.number_up,
        )

        username = user_service.get_username_by_id(str(original_job.user_id), session)

        cups_id = cups_mgr.print_file(
            printer_name=printer.name,
            file_path=file.filepath,
            title=f"{username} free reprint in {printer.name}",
            options=print_options.cups_options
        )
        if not cups_id:
            logger.error(f"Unable to send free reprint of job {original_job.id} to CUPS")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to send print job to CUPS service"
            )

        cups_mgr.get_toner_levels(printer.name)

        pj_create = PrintJobCreate(
            user_id=str(original_job.user_id),
            printer=printer,
            file=file,
            print_options=print_options,
            cost=0,
            pages=original_job.pages,
        )
        new_job = pj_service.create_job(cups_id=cups_id, printjob=pj_create, session=session)
        new_job.free_reprint_of_job_id = original_job.id
        session.add(new_job)
        session.commit()
        session.refresh(new_job)

        tx_data = TransactionCreate(
            user_id=original_job.user_id,
            type=TransactionType.FREE_REPRINT,
            amount=0,
            balance_after=None,
            note=reason,
            actor_id=uuid.UUID(admin_id),
            actor_type=ActorType.ADMIN,
            target_user_id=original_job.user_id,
            related_job_id=new_job.id,
        )
        tx_service.create_transaction(tx_data, session)

        return new_job
