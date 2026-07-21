from datetime import date, datetime, time

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


# Both endpoints take independent, optional start/end dates rather than a
# fixed "period" enum, so the same params serve both client-computed presets
# (last 7/30/90 days, this year) and an arbitrary custom range. Omitting
# both keeps the endpoint's behavior byte-for-byte identical to before this
# was added — a pure opt-in.
def _date_bounds(start_date: date | None, end_date: date | None):
    start_dt = datetime.combine(start_date, time.min) if start_date else None
    end_dt = datetime.combine(end_date, time.max) if end_date else None
    return start_dt, end_dt


def _apply_range(stmt, column, start_dt, end_dt):
    if start_dt is not None:
        stmt = stmt.where(column >= start_dt)
    if end_dt is not None:
        stmt = stmt.where(column <= end_dt)
    return stmt


@router.get(
    "/me",
    response_model=UserPersonalStats,
    status_code=status.HTTP_200_OK
)
def get_my_stats(
    token: TokenDep,
    session: SessionDep,
    start_date: date | None = None,
    end_date: date | None = None,
):
    """Return personal printing statistics for the authenticated user.

    Optionally scoped to a date window via start_date/end_date (inclusive) —
    omit both for the all-time totals."""
    user_id = uuid.UUID(token.credentials)
    start_dt, end_dt = _date_bounds(start_date, end_date)

    printer_stmt = (
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
    )
    printer_stmt = _apply_range(printer_stmt, PrintJob.completed_at, start_dt, end_dt)
    printer_rows = session.exec(printer_stmt.group_by(PrintJob.printer_name)).all()

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

    refund_stmt = select(func.sum(Transaction.amount)).where(
        Transaction.user_id == user_id,
        Transaction.type == TransactionType.REFUND,
        Transaction.amount > 0,
    )
    refund_stmt = _apply_range(refund_stmt, Transaction.created_at, start_dt, end_dt)
    total_refunded = session.exec(refund_stmt).one() or 0

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
    session: SessionDep,
    start_date: date | None = None,
    end_date: date | None = None,
):
    """Return aggregated statistics for the admin dashboard (admin only).

    Optionally scoped to a date window via start_date/end_date (inclusive) —
    omit both for the all-time totals. total_current_balance is always a
    live snapshot regardless of the window, since it's a liability, not a
    flow, and can't meaningfully be "as of" a past date."""
    start_dt, end_dt = _date_bounds(start_date, end_date)

    # ── By printer ────────────────────────────────────────────────────────────
    printer_stmt = (
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
    )
    printer_stmt = _apply_range(printer_stmt, PrintJob.completed_at, start_dt, end_dt)
    printer_rows = session.exec(printer_stmt.group_by(PrintJob.printer_name)).all()

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
    user_stmt = (
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
    )
    user_stmt = _apply_range(user_stmt, PrintJob.completed_at, start_dt, end_dt)
    user_rows = session.exec(user_stmt.group_by(PrintJob.user_id, User.username)).all()

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

    finance_stmt = select(Transaction.type, pos_sum, abs_sum, raw_sum).group_by(Transaction.type)
    finance_stmt = _apply_range(finance_stmt, Transaction.created_at, start_dt, end_dt)
    finance_rows = session.exec(finance_stmt).all()
    finance_by_type = {row[0]: row for row in finance_rows}

    def _agg(tx_type, idx):
        row = finance_by_type.get(tx_type)
        return float(row[idx] or 0) if row else 0.0

    total_recharged = _agg(TransactionType.RECHARGE, 1)
    total_spent_on_print = _agg(TransactionType.PRINT, 2)
    total_refunded = _agg(TransactionType.REFUND, 1)
    total_adjustments = _agg(TransactionType.ADJUSTMENT, 3)
    total_expenses = _agg(TransactionType.EXPENSE, 2)
    total_product_purchases = _agg(TransactionType.PRODUCT_PURCHASE, 2)

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
        total_expenses=round(total_expenses, 2),
        total_product_purchases=round(total_product_purchases, 2),
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
