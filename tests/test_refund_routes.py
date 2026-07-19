import uuid

from src.db.models.printerjob import PrintJob, JobStatus
from src.db.models.refund_request import RefundRequest, RefundStatus
from src.db.models.user import UserRole
from tests.conftest import make_token, make_user


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


def make_refund_request(session, user, job, status=RefundStatus.PENDING, **overrides):
    defaults = dict(
        user_id=user.id,
        print_job_id=job.id,
        status=status,
    )
    defaults.update(overrides)
    refund = RefundRequest(**defaults)
    session.add(refund)
    session.commit()
    session.refresh(refund)
    return refund


def test_approve_refund_credits_balance(client, session):
    user = make_user(session, balance=5.0, role=UserRole.USER)
    admin = make_user(session, role=UserRole.ADMIN)
    job = make_completed_job(session, user, cost=1.50)
    refund = make_refund_request(session, user, job)
    admin_token = make_token(admin.id)

    response = client.patch(
        f"/api/refunds/{refund.id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    session.refresh(user)
    assert user.balance == 6.50


def test_resolve_already_resolved_refund_is_conflict(client, session):
    user = make_user(session, balance=5.0)
    admin = make_user(session, role=UserRole.ADMIN)
    job = make_completed_job(session, user, cost=1.50)
    refund = make_refund_request(session, user, job, status=RefundStatus.DENIED)
    admin_token = make_token(admin.id)

    response = client.patch(
        f"/api/refunds/{refund.id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409
