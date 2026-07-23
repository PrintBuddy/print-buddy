import uuid

from src.db.models.printerjob import PrintJob, JobStatus
from src.db.models.refund_request import RefundRequest, RefundStatus
from src.db.models.user import UserRole
from tests.conftest import make_token, make_user
from tests.test_print_routes import make_printer, make_file


def make_completed_job(session, user, cost=1.50, **overrides):
    defaults = dict(
        cups_id=str(uuid.uuid4()),
        user_id=user.id,
        printer_id=uuid.uuid4(),
        printer_name="Printer1",
        pages=5,
        cost=cost,
        status=JobStatus.COMPLETED,
    )
    defaults.update(overrides)
    job = PrintJob(**defaults)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


# ─── Refund override ─────────────────────────────────────────────────────────

def test_non_admin_cannot_override_refund(client, session):
    user = make_user(session, balance=5.0)
    job = make_completed_job(session, user)
    token = make_token(user.id)

    response = client.post(
        f"/api/refunds/override/{job.id}",
        json={"reason": "Printer jammed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_override_refund_requires_reason(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    job = make_completed_job(session, user, cost=1.50)

    response = client.post(
        f"/api/refunds/override/{job.id}",
        json={"reason": ""},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 422


def test_override_refund_credits_balance_and_is_immediately_resolved(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    job = make_completed_job(session, user, cost=1.50)

    response = client.post(
        f"/api/refunds/override/{job.id}",
        json={"reason": "Printer jammed halfway through"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "approved"
    assert body["initiated_by_admin_id"] == str(admin.id)
    assert body["resolved_by_username"] == admin.username

    session.refresh(user)
    assert user.balance == 6.50

    from sqlmodel import select
    from src.db.models.transaction import Transaction, TransactionType
    tx = session.exec(select(Transaction).where(Transaction.type == TransactionType.REFUND)).first()
    assert tx is not None
    assert tx.amount == 1.50
    assert tx.actor_type.value == "admin"


def test_override_refund_rejects_non_completed_job(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    job = make_completed_job(session, user, status=JobStatus.PENDING)

    response = client.post(
        f"/api/refunds/override/{job.id}",
        json={"reason": "test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 422


def test_override_refund_conflicts_with_existing_pending_request(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    job = make_completed_job(session, user)
    session.add(RefundRequest(user_id=user.id, print_job_id=job.id, status=RefundStatus.PENDING))
    session.commit()

    response = client.post(
        f"/api/refunds/override/{job.id}",
        json={"reason": "test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409


# ─── Free reprint ─────────────────────────────────────────────────────────────

def test_non_admin_cannot_free_reprint(client, session):
    user = make_user(session)
    printer = make_printer(session)
    file = make_file(session, user)
    job = make_completed_job(session, user, printer_id=printer.id, file_id=file.id)
    token = make_token(user.id)

    response = client.post(
        f"/api/print/jobs/{job.id}/free-reprint",
        json={"reason": "Bad print quality"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_free_reprint_creates_zero_cost_job_and_ledger_entry(client, session, monkeypatch):
    monkeypatch.setattr("src.core.print_assistant.cups_mgr.print_file", lambda **kwargs: "cups-reprint-1")
    monkeypatch.setattr("src.core.print_assistant.cups_mgr.get_toner_levels", lambda *a, **k: None)

    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    printer = make_printer(session)
    file = make_file(session, user, pages=3)
    job = make_completed_job(session, user, printer_id=printer.id, printer_name=printer.name, file_id=file.id, pages=3)

    response = client.post(
        f"/api/print/jobs/{job.id}/free-reprint",
        json={"reason": "Paper jam on original print"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["cost"] == 0
    assert body["free_reprint_of_job_id"] == str(job.id)

    session.refresh(user)
    assert user.balance == 5.0  # unchanged — no money moves

    from sqlmodel import select
    from src.db.models.transaction import Transaction, TransactionType
    tx = session.exec(select(Transaction).where(Transaction.type == TransactionType.FREE_REPRINT)).first()
    assert tx is not None
    assert tx.amount == 0
    assert tx.note == "Paper jam on original print"
    assert tx.actor_id == admin.id


def test_free_reprint_fails_gracefully_when_file_gone(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    printer = make_printer(session)
    # file_id left unset — simulates the file having already been cleaned
    # up by the 24h file-retention job.
    job = make_completed_job(session, user, printer_id=printer.id, printer_name=printer.name)

    response = client.post(
        f"/api/print/jobs/{job.id}/free-reprint",
        json={"reason": "test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409
