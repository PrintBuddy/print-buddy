from fastapi import APIRouter, status
from sqlmodel import select
import uuid

from ..dependencies.token import AdminTokenDep, TokenDep
from ..dependencies.database import SessionDep

from sqlmodel import func
from sqlalchemy import case, cast, String

from ...db.models.printerjob import PrintJob, JobStatus
from ...db.models.transaction import Transaction, TransactionType
from ...db.models.user import User

from ...schemas.stats import GlobalStats, PrinterPageStats, UserPageStats, FinanceStats, UserPersonalStats


router = APIRouter()


# `(pages + 1) / 2` is `ceil(pages / 2)` for positive integers, computed via
# plain integer division so it's portable across Postgres and SQLite (the
# test suite's engine) without relying on a SQL CEIL() function.
def _sheets_expr():
    return case((PrintJob.two_sided, (PrintJob.pages + 1) / 2), else_=PrintJob.pages)


def _bw_expr():
    return case((PrintJob.color.is_(False), PrintJob.pages), else_=0)


def _color_expr():
    return case((PrintJob.color.is_(True), PrintJob.pages), else_=0)


@router.get(
    "/me",
    response_model=UserPersonalStats,
    status_code=status.HTTP_200_OK
)
def get_my_stats(
    token: TokenDep,
    session: SessionDep
):
    """Return personal printing statistics for the authenticated user."""
    user_id = uuid.UUID(token.credentials)

    printer_rows = session.exec(
        select(
            PrintJob.printer_name,
            func.sum(PrintJob.pages),
            func.sum(_bw_expr()),
            func.sum(_color_expr()),
            func.sum(_sheets_expr()),
            func.sum(PrintJob.cost),
            func.count(),
        )
        .where(
            PrintJob.user_id == user_id,
            PrintJob.status == JobStatus.COMPLETED,
        )
        .group_by(PrintJob.printer_name)
    ).all()

    by_printer = [
        PrinterPageStats(
            printer_name=name,
            total_pages=int(pages or 0),
            bw_pages=int(bw or 0),
            color_pages=int(color or 0),
            total_sheets=int(sheets or 0),
            total_cost=round(float(cost or 0), 2),
        )
        for name, pages, bw, color, sheets, cost, _jobs in printer_rows
    ]
    by_printer.sort(key=lambda x: x.total_pages, reverse=True)

    total_pages = sum(int(row[1] or 0) for row in printer_rows)
    bw_pages = sum(int(row[2] or 0) for row in printer_rows)
    color_pages = sum(int(row[3] or 0) for row in printer_rows)
    total_sheets = sum(int(row[4] or 0) for row in printer_rows)
    total_jobs = sum(int(row[6]) for row in printer_rows)
    total_cost_sum = sum(float(row[5] or 0) for row in printer_rows)

    total_refunded = session.exec(
        select(func.sum(Transaction.amount)).where(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.REFUND,
            Transaction.amount > 0,
        )
    ).one() or 0

    total_spent = round(max(total_cost_sum - total_refunded, 0), 2)

    return UserPersonalStats(
        total_pages=total_pages,
        bw_pages=bw_pages,
        color_pages=color_pages,
        total_sheets=total_sheets,
        total_jobs=total_jobs,
        total_spent=total_spent,
        by_printer=by_printer,
    )


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

    # ── By printer ────────────────────────────────────────────────────────────
    printer_rows = session.exec(
        select(
            PrintJob.printer_name,
            func.sum(PrintJob.pages),
            func.sum(_bw_expr()),
            func.sum(_color_expr()),
            func.sum(_sheets_expr()),
            func.sum(PrintJob.cost),
            func.count(),
        )
        .where(PrintJob.status == JobStatus.COMPLETED)
        .group_by(PrintJob.printer_name)
    ).all()

    by_printer = [
        PrinterPageStats(
            printer_name=name,
            total_pages=int(pages or 0),
            bw_pages=int(bw or 0),
            color_pages=int(color or 0),
            total_sheets=int(sheets or 0),
            total_cost=round(float(cost or 0), 2),
        )
        for name, pages, bw, color, sheets, cost, _jobs in printer_rows
    ]
    by_printer.sort(key=lambda x: x.total_pages, reverse=True)

    total_pages = sum(int(row[1] or 0) for row in printer_rows)
    bw_pages = sum(int(row[2] or 0) for row in printer_rows)
    color_pages = sum(int(row[3] or 0) for row in printer_rows)
    total_sheets = sum(int(row[4] or 0) for row in printer_rows)
    total_jobs = sum(int(row[6]) for row in printer_rows)

    # ── By user ───────────────────────────────────────────────────────────────
    user_rows = session.exec(
        select(
            PrintJob.user_id,
            func.coalesce(User.username, cast(PrintJob.user_id, String)),
            func.sum(PrintJob.pages),
            func.sum(_bw_expr()),
            func.sum(_color_expr()),
            func.sum(_sheets_expr()),
        )
        .outerjoin(User, User.id == PrintJob.user_id)
        .where(PrintJob.status == JobStatus.COMPLETED)
        .group_by(PrintJob.user_id, User.username)
    ).all()

    by_user = [
        UserPageStats(
            user_id=str(uid),
            username=username,
            total_pages=int(pages or 0),
            bw_pages=int(bw or 0),
            color_pages=int(color or 0),
            total_sheets=int(sheets or 0),
        )
        for uid, username, pages, bw, color, sheets in user_rows
    ]
    by_user.sort(key=lambda x: x.total_pages, reverse=True)

    # ── Finance ───────────────────────────────────────────────────────────────
    # One row per TransactionType present in the data, instead of loading
    # every transaction into Python to filter/sum per type.
    pos_sum = func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0))
    abs_sum = func.sum(func.abs(Transaction.amount))
    raw_sum = func.sum(Transaction.amount)

    finance_rows = session.exec(
        select(Transaction.type, pos_sum, abs_sum, raw_sum).group_by(Transaction.type)
    ).all()
    finance_by_type = {row[0]: row for row in finance_rows}

    def _agg(tx_type, idx):
        row = finance_by_type.get(tx_type)
        return float(row[idx] or 0) if row else 0.0

    total_recharged = _agg(TransactionType.RECHARGE, 1)
    total_spent_on_print = _agg(TransactionType.PRINT, 2)
    total_refunded = _agg(TransactionType.REFUND, 1)
    total_adjustments = _agg(TransactionType.ADJUSTMENT, 3)

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
