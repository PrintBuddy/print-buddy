from fastapi import APIRouter, status, HTTPException
import uuid
import math

from ..dependencies.token import TokenDep, AdminTokenDep
from ..dependencies.database import SessionDep
from ..dependencies.pagination import PaginationDep

from ...schemas.print import PrintOptions
from ...schemas.printjob import PrintJobCreate, PrintJobRead, PrintJobAdminRead, FreeReprintCreate

from ...db.crud.printjob import PrintJobService
from ...db.crud.group import GroupService

from ...core.utils import count_pages_in_range, round_money
from ...core.print_assistant import PrintAssistant
from ...core.logger import logger


router = APIRouter()

print_assistant = PrintAssistant()
pj_service = PrintJobService()
group_service = GroupService()


@router.get(
    '/my-jobs',
    response_model=list[PrintJobRead],
    status_code=status.HTTP_200_OK
)
def get_my_jobs(
    token: TokenDep,
    session: SessionDep,
    pagination: PaginationDep
):
    user_id = token.credentials
    jobs = pj_service.get_jobs_by_id(user_id, session, pagination.limit, pagination.offset)
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

    # CHECK USER HAS ACCESS TO RESTRICTED PRINTERS
    if printer.is_restricted:
        if not group_service.user_can_access_printer(uuid.UUID(user_id), printer.id, session):
            logger.error(f"User {user_id} has no access to restricted printer {printer_name}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this printer"
            )

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

    # CALCULATE PRICE — apply group custom prices if available
    effective_bw, effective_color = group_service.get_effective_prices(
        uuid.UUID(user_id), printer.id, session
    )
    if color:
        price_per_page = (
            effective_color
            if effective_color is not None
            else printer.price_per_page_color
        )
    else:
        price_per_page = (
            effective_bw
            if effective_bw is not None
            else printer.price_per_page_bw
        )
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

    # Calculate effective pages accounting for n-up (pages per sheet)
    # e.g., 4 pages with 2-up = 2 physical sheets
    effective_pages = math.ceil(pages / print_options.number_up)
    total_price = round_money(effective_pages * print_options.copies * price_per_page)

    # SEND JOB — send_print_job atomically debits credit before sending to
    # CUPS and raises 402/404 itself if the debit fails, so no separate
    # pre-check is done here (that would just reopen the race it closes).
    pj_create = PrintJobCreate(
        user_id=user_id,
        printer=printer,
        file=file,
        print_options=print_options,
        cost=total_price,
        pages=effective_pages * print_options.copies
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
    session: SessionDep,
    pagination: PaginationDep
):
    """Get all print jobs across all users (admin only)."""
    return pj_service.get_all_jobs(session, pagination.limit, pagination.offset)


@router.post(
    '/jobs/{job_id}/free-reprint',
    response_model=PrintJobAdminRead,
    status_code=status.HTTP_201_CREATED
)
def free_reprint(
    job_id: str,
    data: FreeReprintCreate,
    token: AdminTokenDep,
    session: SessionDep
):
    """Re-sends an earlier job at no cost — a customer-service gesture,
    e.g. a paper jam or print-quality issue. Every reprint requires a
    reason and leaves an immutable, zero-amount FREE_REPRINT Transaction
    for audit visibility even though no money moves."""
    admin_id = token.credentials

    original_job = pj_service.get_job_by_id(job_id, session)
    if original_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Print job not found")

    return print_assistant.send_free_reprint(original_job, admin_id, data.reason, session)
