import uuid

from src.db.models.file import File
from src.db.models.printer import Printer
from tests.conftest import make_token, make_user


def make_printer(session, **overrides):
    defaults = dict(
        name=f"printer_{uuid.uuid4().hex[:8]}",
        price_per_page_bw=0.10,
        price_per_page_color=0.50,
        admits_color=True,
        is_active=True,
    )
    defaults.update(overrides)
    printer = Printer(**defaults)
    session.add(printer)
    session.commit()
    session.refresh(printer)
    return printer


def make_file(session, user, pages=10, **overrides):
    defaults = dict(
        user_id=user.id,
        filename="doc.pdf",
        filepath="/tmp/doc.pdf",
        size_bytes=1024,
        mime_type="application/pdf",
        pages=pages,
    )
    defaults.update(overrides)
    file = File(**defaults)
    session.add(file)
    session.commit()
    session.refresh(file)
    return file


def test_print_debits_balance_and_creates_transaction(client, session, monkeypatch):
    monkeypatch.setattr("src.core.print_assistant.cups_mgr.print_file", lambda **kwargs: "cups-job-1")
    monkeypatch.setattr("src.core.print_assistant.cups_mgr.get_toner_levels", lambda *a, **k: None)

    user = make_user(session, balance=10.0, credit_limit=0.0)
    printer = make_printer(session, price_per_page_bw=0.10)
    file = make_file(session, user, pages=10)
    token = make_token(user.id)

    response = client.post(
        f"/api/print/{printer.name}/{file.id}",
        json={"copies": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    expected_cost = 10 * 0.10  # 10 pages * $0.10/page, 1 copy
    session.refresh(user)
    assert user.balance == round(10.0 - expected_cost, 2)


def test_print_insufficient_balance_rejected(client, session, monkeypatch):
    monkeypatch.setattr("src.core.print_assistant.cups_mgr.print_file", lambda **kwargs: "cups-job-2")
    monkeypatch.setattr("src.core.print_assistant.cups_mgr.get_toner_levels", lambda *a, **k: None)

    user = make_user(session, balance=0.05, credit_limit=0.0)
    printer = make_printer(session, price_per_page_bw=0.10)
    file = make_file(session, user, pages=10)
    token = make_token(user.id)

    response = client.post(
        f"/api/print/{printer.name}/{file.id}",
        json={"copies": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 402
    session.refresh(user)
    assert user.balance == 0.05


def test_print_zero_copies_rejected(client, session):
    user = make_user(session, balance=10.0, credit_limit=0.0)
    printer = make_printer(session)
    file = make_file(session, user, pages=10)
    token = make_token(user.id)

    response = client.post(
        f"/api/print/{printer.name}/{file.id}",
        json={"copies": 0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
