from fastapi import APIRouter, status
from math import ceil
from sqlmodel import select

from ..dependencies.token import AdminTokenDep
from ..dependencies.database import SessionDep

from sqlmodel import func

from ...db.models.printerjob import PrintJob, JobStatus
from ...db.models.transaction import Transaction, TransactionType
from ...db.models.user import User

from ...schemas.stats import GlobalStats, PrinterPageStats, UserPageStats, FinanceStats


router = APIRouter()


@router.get(
    "/overview",
    response_model=GlobalStats,
    status_code=status.HTTP_200_OK
)
def get_stats_overview(
    token: AdminTokenDep,
    session: SessionDep
):
    """Return aggregated statistics for the admin dashboard (admin only)."""

    # ── Print jobs ────────────────────────────────────────────────────────────
    jobs = list(session.exec(
        select(PrintJob).where(PrintJob.status == JobStatus.COMPLETED)
    ).all())

    total_pages = sum(j.pages for j in jobs)
    bw_pages = sum(j.pages for j in jobs if not j.color)
    color_pages = sum(j.pages for j in jobs if j.color)
    total_jobs = len(jobs)

    def job_sheets(job: PrintJob) -> int:
        return ceil(job.pages / 2) if job.two_sided else job.pages

    total_sheets = sum(job_sheets(j) for j in jobs)

    # ── By printer ────────────────────────────────────────────────────────────
    printer_stats: dict[str, dict] = {}
    for job in jobs:
        name = job.printer_name
        if name not in printer_stats:
            printer_stats[name] = {"total_pages": 0, "bw_pages": 0, "color_pages": 0, "total_sheets": 0, "total_cost": 0.0}
        printer_stats[name]["total_pages"] += job.pages
        printer_stats[name]["total_sheets"] += job_sheets(job)
        printer_stats[name]["total_cost"] += job.cost
        if job.color:
            printer_stats[name]["color_pages"] += job.pages
        else:
            printer_stats[name]["bw_pages"] += job.pages

    by_printer = [
        PrinterPageStats(printer_name=k, **{**v, "total_cost": round(v["total_cost"], 2)})
        for k, v in printer_stats.items()
    ]
    by_printer.sort(key=lambda x: x.total_pages, reverse=True)

    # ── By user ───────────────────────────────────────────────────────────────
    user_id_set = {j.user_id for j in jobs}
    users_in_db: dict = {}
    if user_id_set:
        db_users = session.exec(select(User).where(User.id.in_(user_id_set))).all()
        users_in_db = {u.id: u for u in db_users}

    user_stats: dict[str, dict] = {}
    for job in jobs:
        uid = str(job.user_id)
        if uid not in user_stats:
            user_obj = users_in_db.get(job.user_id)
            username = user_obj.username if user_obj else uid
            user_stats[uid] = {
                "username": username,
                "total_pages": 0,
                "bw_pages": 0,
                "color_pages": 0,
                "total_sheets": 0,
            }
        user_stats[uid]["total_pages"] += job.pages
        user_stats[uid]["total_sheets"] += job_sheets(job)
        if job.color:
            user_stats[uid]["color_pages"] += job.pages
        else:
            user_stats[uid]["bw_pages"] += job.pages

    by_user = [
        UserPageStats(user_id=k, **v)
        for k, v in user_stats.items()
    ]
    by_user.sort(key=lambda x: x.total_pages, reverse=True)

    # ── Finance ───────────────────────────────────────────────────────────────
    transactions = list(session.exec(select(Transaction)).all())

    total_recharged = sum(
        t.amount for t in transactions
        if t.type == TransactionType.RECHARGE and t.amount > 0
    )
    total_spent_on_print = sum(
        abs(t.amount) for t in transactions
        if t.type == TransactionType.PRINT
    )
    total_refunded = sum(
        t.amount for t in transactions
        if t.type == TransactionType.REFUND and t.amount > 0
    )
    total_adjustments = sum(
        t.amount for t in transactions
        if t.type == TransactionType.ADJUSTMENT
    )

    # Sum of current balances across all users
    total_current_balance_result = session.exec(
        select(func.sum(User.balance))
    ).one()
    total_current_balance = total_current_balance_result or 0.0

    finance = FinanceStats(
        total_recharged=round(total_recharged, 2),
        total_current_balance=round(total_current_balance, 2),
        total_spent_on_print=round(total_spent_on_print, 2),
        total_refunded=round(total_refunded, 2),
        total_adjustments=round(total_adjustments, 2),
    )

    return GlobalStats(
        total_pages=total_pages,
        bw_pages=bw_pages,
        color_pages=color_pages,
        total_sheets=total_sheets,
        total_jobs=total_jobs,
        by_printer=by_printer,
        by_user=by_user,
        finance=finance,
    )
