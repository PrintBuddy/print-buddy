import uuid

from src.core.scheduler import Scheduler
from src.db.crud.inventory import InventoryService
from src.db.models.inventory import InventoryCategory
from src.db.models.telegram_admin import TelegramAdmin
from src.db.models.user import UserRole
from tests.conftest import make_user


class FakeJob:
    def __init__(self, printer_id, pages):
        self.id = uuid.uuid4()
        self.printer_id = printer_id
        self.pages = pages


def test_decrement_paper_stock_prefers_printer_specific_item(session):
    scheduler = Scheduler()
    inventory_service = InventoryService()
    printer_id = uuid.uuid4()

    global_item = inventory_service.create_item(
        "Shared Paper", InventoryCategory.PAPER, "sheets", 100, session, initial_stock=1000
    )
    specific_item = inventory_service.create_item(
        "Printer 1 Paper", InventoryCategory.PAPER, "sheets", 100, session,
        initial_stock=500, printer_id=str(printer_id),
    )

    job = FakeJob(printer_id=printer_id, pages=10)
    scheduler._decrement_paper_stock(job, session)

    session.refresh(global_item)
    session.refresh(specific_item)
    assert specific_item.current_stock == 490.0
    assert global_item.current_stock == 1000.0  # untouched


def test_decrement_paper_stock_falls_back_to_global_item(session):
    scheduler = Scheduler()
    inventory_service = InventoryService()

    global_item = inventory_service.create_item(
        "Shared Paper", InventoryCategory.PAPER, "sheets", 100, session, initial_stock=1000
    )

    job = FakeJob(printer_id=uuid.uuid4(), pages=25)
    scheduler._decrement_paper_stock(job, session)

    session.refresh(global_item)
    assert global_item.current_stock == 975.0


def test_decrement_paper_stock_noop_when_no_item_configured(session):
    scheduler = Scheduler()
    job = FakeJob(printer_id=uuid.uuid4(), pages=10)
    # Should not raise even though no InventoryItem exists at all.
    scheduler._decrement_paper_stock(job, session)


def test_check_low_stock_sync_notifies_once_then_debounces(session, engine, monkeypatch):
    monkeypatch.setattr("src.core.scheduler.engine", engine)

    admin = make_user(session, role=UserRole.ADMIN)
    session.add(TelegramAdmin(user_id=admin.id, telegram_id="555"))
    session.commit()

    inventory_service = InventoryService()
    inventory_service.create_item(
        "Low Item", InventoryCategory.PAPER, "sheets", 100, session, initial_stock=50
    )

    scheduler = Scheduler()

    sent = []
    monkeypatch.setattr(
        "src.core.scheduler.telegram_notifier.send_message",
        lambda chat_id, text: sent.append((chat_id, text)),
    )

    result_1 = scheduler.check_low_stock_sync()
    assert result_1 is not None
    assert result_1[0]["chat_ids"] == ["555"]
    assert len(result_1[0]["alerts"]) == 1

    # Immediately checking again should NOT re-notify (debounced).
    result_2 = scheduler.check_low_stock_sync()
    assert result_2 is None
