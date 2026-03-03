from fastapi import APIRouter, status, HTTPException

from ..dependencies.token import TokenDep, AdminTokenDep
from ..dependencies.database import SessionDep

from ...schemas.print import PrintOptions
from ...schemas.printjob import PrintJobCreate, PrintJobRead, PrintJobAdminRead

from ...db.crud.printjob import PrintJobService

from ...core.utils import count_pages_in_range
from ...core.print_assistant import PrintAssistant
from ...core.logger import logger


router = APIRouter()

print_assistant = PrintAssistant()
pj_service = PrintJobService()


@router.get(
    '/my-jobs',
    response_model=list[PrintJobRead],
    status_code=status.HTTP_200_OK
)
def get_my_jobs(
    token: TokenDep,
    session: SessionDep
):
    user_id = token.credentials
    jobs = pj_service.get_jobs_by_id(user_id, session)
    return jobs


@router.post(
    '/{printer_name}/{file_id}',
    response_model=PrintJobRead,
    status_code=status.HTTP_200_OK
)
def print_file(
    printer_name: str,
    file_id: str,
    print_options: PrintOptions,
    token: TokenDep,
    session: SessionDep
):
    user_id = token.credentials

    # VERIFY PRINTER'S EXISTENCE
    printer = print_assistant.get_printer(printer_name, session)

    # VERIFY FILE'S EXISTENCE AND BELONGING
    file = print_assistant.get_file_to_print(user_id, file_id, session)

    # VERIFY PRINT OPTIONS COMPLIANCE (COLOR)
    color = print_options.color
    if color and not printer.admits_color:
        logger.error(f"Printer {printer_name} does not admit color")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Printer does not admit color"
        )

    # CALCULATE PRICE
    price_per_page = printer.price_per_page_color if color else printer.price_per_page_bw
    if print_options.page_ranges == "all":
        pages = file.pages
    else:
        pages = count_pages_in_range(print_options.page_ranges, file.pages)

    if pages == 0:
        logger.error(f"Invalid format of page-ranges: {print_options.page_ranges}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid format of page-ranges"
        )

    total_price = pages * print_options.copies * price_per_page

    # VERIFY ENOUGH USER CREDITS
    enough_credits = print_assistant.check_enough_credit(user_id, total_price, session)
    if not enough_credits:
        logger.error(f"User {user_id} has insufficient balance to print")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient balance to print"
        )

    # SEND JOB AND DISCOUNT IF JOB SENT
    pj_create = PrintJobCreate(
        user_id=user_id,
        printer=printer,
        file=file,
        print_options=print_options,
        cost=total_price,
        pages=pages
    )

    pj = print_assistant.send_print_job(
        printjob=pj_create,
        session=session
    )

    return pj


@router.get(
    '/all-jobs',
    response_model=list[PrintJobAdminRead],
    status_code=status.HTTP_200_OK
)
def get_all_jobs(
    token: AdminTokenDep,
    session: SessionDep
):
    """Get all print jobs across all users (admin only)."""
    return pj_service.get_all_jobs(session)