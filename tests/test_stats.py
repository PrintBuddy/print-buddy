import uuid
from dataclasses import dataclass

from src.api.routes.stats import get_my_stats, get_stats_overview
from src.db.models.printerjob import PrintJob, JobStatus
from src.db.models.transaction import Transaction, TransactionType
from src.db.models.user import User


@dataclass
class FakeToken:
    credentials: str


def make_user(session, **overrides):
    defaults = dict(
        username=f"user_{uuid.uuid4().hex[:8]}",
        name="Test",
        surname="User",
        pwd="secret",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        balance=0.0,
        credit_limit=0.0,
    )
    defaults.update(overrides)
    user = User(**defaults)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def make_job(session, user, printer_name, pages, color, two_sided, cost, status=JobStatus.COMPLETED):
    job = PrintJob(
        cups_id=str(uuid.uuid4()),
        user_id=user.id,
        printer_id=uuid.uuid4(),
        printer_name=printer_name,
        pages=pages,
        color=color,
        two_sided=two_sided,
        cost=cost,
        status=status,
    )
    session.add(job)
    session.commit()
    return job


def make_transaction(session, user, tx_type, amount):
    tx = Transaction(
        user_id=user.id,
        type=tx_type,
        amount=amount,
        balance_after=0.0,
    )
    session.add(tx)
    session.commit()
    return tx


def seed_data(session):
    user_a = make_user(session, username="user_a", balance=15.00)
    user_b = make_user(session, username="user_b", balance=25.00)

    # user_a's jobs
    make_job(session, user_a, "Printer1", pages=10, color=False, two_sided=False, cost=1.00)
    make_job(session, user_a, "Printer1", pages=5, color=True, two_sided=True, cost=2.50)
    make_job(session, user_a, "Printer2", pages=8, color=False, two_sided=True, cost=0.80)
    # not completed — must be excluded from every aggregate
    make_job(session, user_a, "Printer1", pages=100, color=False, two_sided=False, cost=99.0, status=JobStatus.PENDING)

    # user_b's jobs
    make_job(session, user_b, "Printer1", pages=20, color=True, two_sided=False, cost=4.00)
    make_job(session, user_b, "Printer2", pages=7, color=False, two_sided=True, cost=0.70)

    # user_a's transactions
    make_transaction(session, user_a, TransactionType.REFUND, 0.50)
    make_transaction(session, user_a, TransactionType.REFUND, -0.20)
    make_transaction(session, user_a, TransactionType.PRINT, -4.30)
    make_transaction(session, user_a, TransactionType.ADJUSTMENT, 3.00)
    make_transaction(session, user_a, TransactionType.ADJUSTMENT, -1.00)

    # user_b's transactions
    make_transaction(session, user_b, TransactionType.RECHARGE, 10.00)
    make_transaction(session, user_b, TransactionType.RECHARGE, -2.00)

    return user_a, user_b


def test_get_my_stats(session):
    user_a, _user_b = seed_data(session)

    stats = get_my_stats(FakeToken(str(user_a.id)), session)

    assert stats.total_pages == 23
    assert stats.bw_pages == 18
    assert stats.color_pages == 5
    assert stats.total_sheets == 17  # 10 + ceil(5/2)=3 + ceil(8/2)=4
    assert stats.total_jobs == 3
    assert stats.total_spent == 3.80  # (1.00+2.50+0.80) - 0.50 refunded

    by_printer = {p.printer_name: p for p in stats.by_printer}
    assert by_printer["Printer1"].total_pages == 15
    assert by_printer["Printer1"].bw_pages == 10
    assert by_printer["Printer1"].color_pages == 5
    assert by_printer["Printer1"].total_sheets == 13
    assert by_printer["Printer1"].total_cost == 3.50

    assert by_printer["Printer2"].total_pages == 8
    assert by_printer["Printer2"].total_sheets == 4
    assert by_printer["Printer2"].total_cost == 0.80

    # sorted descending by total_pages
    assert [p.printer_name for p in stats.by_printer] == ["Printer1", "Printer2"]


def test_get_stats_overview(session):
    user_a, user_b = seed_data(session)

    stats = get_stats_overview(FakeToken(str(user_a.id)), session)

    assert stats.total_pages == 50
    assert stats.bw_pages == 25
    assert stats.color_pages == 25
    assert stats.total_sheets == 41
    assert stats.total_jobs == 5

    by_printer = {p.printer_name: p for p in stats.by_printer}
    assert by_printer["Printer1"].total_pages == 35
    assert by_printer["Printer1"].bw_pages == 10
    assert by_printer["Printer1"].color_pages == 25
    assert by_printer["Printer1"].total_sheets == 33
    assert by_printer["Printer1"].total_cost == 7.50

    assert by_printer["Printer2"].total_pages == 15
    assert by_printer["Printer2"].bw_pages == 15
    assert by_printer["Printer2"].total_sheets == 8
    assert by_printer["Printer2"].total_cost == 1.50

    by_user = {u.username: u for u in stats.by_user}
    assert by_user["user_a"].total_pages == 23
    assert by_user["user_a"].bw_pages == 18
    assert by_user["user_a"].color_pages == 5
    assert by_user["user_a"].total_sheets == 17

    assert by_user["user_b"].total_pages == 27
    assert by_user["user_b"].bw_pages == 7
    assert by_user["user_b"].color_pages == 20
    assert by_user["user_b"].total_sheets == 24

    # sorted descending by total_pages
    assert [u.username for u in stats.by_user] == ["user_b", "user_a"]

    finance = stats.finance
    assert finance.total_recharged == 10.00
    assert finance.total_spent_on_print == 4.30
    assert finance.total_refunded == 0.50
    assert finance.total_adjustments == 2.00
    assert finance.total_current_balance == 40.00
