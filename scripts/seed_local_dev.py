"""Populates a local Postgres database with synthetic data for manually
testing the financial-overhaul feature branch end to end. Uses real
service functions (LedgerService, RechargeRequestResolver, etc.) wherever
one exists, so seeded data is created the same way the app would create
it, not by hand-crafting rows that skip business logic.

DELIBERATELY NEVER TOUCHES NEON — DB connection is taken entirely from
environment variables, which must point at a disposable local database.
Run with:

    export DB_SCHEME=postgresql+psycopg DB_HOSTNAME=localhost \
           DB_USER=rbenatuilv DB_PASSWORD=localtest123 DB_NAME=printbuddy_local
    python -m scripts.seed_local_dev

NOT safely re-runnable in place: the append-only trigger on `transaction`
(and `collectionevent`) blocks DELETEs, by design. To reseed from scratch,
drop and recreate the local database and re-run migrations first:

    psql -U rbenatuilv -h localhost -d postgres \
        -c 'DROP DATABASE "printbuddy_local-dev";' \
        -c 'CREATE DATABASE "printbuddy_local-dev" OWNER rbenatuilv;'
    alembic upgrade head
    python -m scripts.seed_local_dev
"""
import uuid
from datetime import timedelta

from sqlmodel import Session, select

from src.db.main import engine
from src.core.utils import generate_time
from src.core.security import Security
from src.core.recharge_request_service import recharge_request_resolver
from src.core.ledger_service import LedgerService

from src.db.models.user import User, UserRole
from src.db.models.printer import Printer, PrinterStatus
from src.db.models.telegram_admin import TelegramAdmin
from src.db.models.printerjob import PrintJob, JobStatus
from src.db.models.transaction import Transaction, TransactionType, ActorType
from src.db.models.recharge_request import RechargeRequest, RechargeRequestStatus, RechargeMethod
from src.db.models.refund_request import RefundRequest, RefundStatus
from src.db.models.expense import ExpenseCategory
from src.db.models.inventory import InventoryCategory
from src.db.models.product import Product

from src.db.crud.inventory import InventoryService
from src.db.crud.expense import ExpenseService
from src.db.crud.refund_request import RefundRequestService
from src.db.crud.collection_event import CollectionEventService
from src.db.crud.user import UserService
from src.schemas.refund import RefundRequestCreate

if "neon" in engine.url.host:
    raise RuntimeError(
        f"Refusing to seed — DB host '{engine.url.host}' looks like Neon, not a local database."
    )

ledger_service = LedgerService()
inventory_service = InventoryService()
expense_service = ExpenseService()
refund_service = RefundRequestService()
collection_service = CollectionEventService()

PWD = "TestPass123!"
now = generate_time()


def main():
    with Session(engine) as session:
        # ─── Users ──────────────────────────────────────────────────────
        superadmin = User(
            email="superadmin@example.com", username="superadmin",
            name="Sofia", surname="Superadmin", pwd=Security.hash_password(PWD),
            role=UserRole.SUPER_ADMIN, balance=0.0,
        )
        admin_ana = User(
            email="ana@example.com", username="admin_ana",
            name="Ana", surname="Reyes", pwd=Security.hash_password(PWD),
            role=UserRole.ADMIN, balance=0.0,
        )
        admin_leo = User(
            email="leo@example.com", username="admin_leo",
            name="Leo", surname="Duarte", pwd=Security.hash_password(PWD),
            role=UserRole.ADMIN, balance=0.0,
        )
        alice = User(
            email="alice@example.com", username="alice_p",
            name="Alice", surname="Pardo", pwd=Security.hash_password(PWD),
            balance=12.50,
        )
        bruno = User(
            email="bruno@example.com", username="bruno_g",
            name="Bruno", surname="Gil", pwd=Security.hash_password(PWD),
            balance=3.20, credit_limit=5.0,
        )
        carla = User(
            email="carla@example.com", username="carla_m",
            name="Carla", surname="Marin", pwd=Security.hash_password(PWD),
            balance=-1.75, credit_limit=5.0,
        )
        diego = User(
            email="diego@example.com", username="diego_s",
            name="Diego", surname="Soto", pwd=Security.hash_password(PWD),
            balance=25.00,
        )
        elena = User(
            email="elena@example.com", username="elena_r",
            name="Elena", surname="Ruiz", pwd=Security.hash_password(PWD),
            balance=0.0,
        )
        fabio = User(
            email="fabio@example.com", username="fabio_t",
            name="Fabio", surname="Torres", pwd=Security.hash_password(PWD),
            balance=8.00,
        )
        users = [superadmin, admin_ana, admin_leo, alice, bruno, carla, diego, elena, fabio]
        session.add_all(users)
        session.commit()
        for u in users:
            session.refresh(u)

        # ─── Telegram admins (fake IDs — no real Telegram chat behind them) ──
        ta_ana = TelegramAdmin(
            user_id=admin_ana.id, telegram_id="1111111111",
            phone_number="+34 600 111 222", accepts_transfer=True,
            bank_name="Ana Reyes", bank_iban="ES00 0000 0000 0000 0000 0000",
            bank_link="https://example.test/pay/ana",
        )
        ta_leo = TelegramAdmin(
            user_id=admin_leo.id, telegram_id="2222222222",
            phone_number="+34 600 333 444", accepts_transfer=False,
        )
        session.add_all([ta_ana, ta_leo])
        session.commit()
        session.refresh(ta_ana)
        session.refresh(ta_leo)

        # ─── Printers ───────────────────────────────────────────────────
        printer_bw = Printer(
            name="OfficeJet - Common Room", location="Common Room", status=PrinterStatus.IDLE,
            price_per_page_bw=0.05, admits_color=False, supports_duplex=True,
        )
        printer_color = Printer(
            name="LaserColor - Library", location="Library", status=PrinterStatus.IDLE,
            price_per_page_bw=0.05, admits_color=True, price_per_page_color=0.15, supports_duplex=True,
        )
        # Matches the name of the real CUPS "PDF" virtual printer this
        # machine has available — the only one of the three that can
        # actually accept a live print submission end to end (needed to
        # manually test the print flow, free reprint, etc., not just the
        # financial routes).
        printer_pdf = Printer(
            name="PDF", location="Lab 1", status=PrinterStatus.IDLE,
            price_per_page_bw=0.05, admits_color=True, price_per_page_color=0.10, supports_duplex=True,
        )
        session.add_all([printer_bw, printer_color, printer_pdf])
        session.commit()
        session.refresh(printer_bw)
        session.refresh(printer_color)
        session.refresh(printer_pdf)

        # ─── Print jobs (direct insert — bypasses CUPS, which isn't
        # available locally) + matching PRINT debit transactions ──────────
        def make_completed_job(user, printer, pages, color, days_ago):
            cost = round(pages * (printer.price_per_page_color if color else printer.price_per_page_bw), 2)
            created = now - timedelta(days=days_ago)
            job = PrintJob(
                cups_id=f"local-{uuid.uuid4().hex[:8]}",
                user_id=user.id, printer_id=printer.id, printer_name=printer.name,
                file_name=f"document-{uuid.uuid4().hex[:4]}.pdf", file_size=204800,
                pages=pages, color=color, status=JobStatus.COMPLETED,
                cost=cost, created_at=created, completed_at=created + timedelta(minutes=2),
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            new_balance = UserService().adjust_balance(str(user.id), -cost, session, enforce_credit_limit=True)
            tx = Transaction(
                user_id=user.id, type=TransactionType.PRINT, amount=-cost,
                balance_after=new_balance.new_balance, actor_id=user.id, actor_type=ActorType.USER,
                target_user_id=user.id, related_job_id=job.id, note=f"Print job on {printer.name}",
                created_at=created,
            )
            session.add(tx)
            session.commit()
            return job

        job_alice_1 = make_completed_job(alice, printer_bw, 12, False, 6)
        make_completed_job(alice, printer_color, 4, True, 2)
        job_bruno_1 = make_completed_job(bruno, printer_bw, 30, False, 5)
        job_diego_1 = make_completed_job(diego, printer_color, 8, True, 1)
        make_completed_job(fabio, printer_bw, 5, False, 3)

        # ─── Recharge requests ──────────────────────────────────────────
        # Two still pending, awaiting resolution in the web queue / Telegram.
        rr_pending_web = RechargeRequest(
            user_id=elena.id, username=elena.username, amount=15.0,
            message="Paid cash at reception", status=RechargeRequestStatus.PENDING,
            method=RechargeMethod.CASH, target_telegram_admin_id=ta_ana.id,
        )
        rr_pending_transfer = RechargeRequest(
            user_id=fabio.id, username=fabio.username, amount=20.0,
            message="Bank transfer sent this morning", status=RechargeRequestStatus.PENDING,
            method=RechargeMethod.TRANSFER, target_telegram_admin_id=ta_leo.id,
        )
        session.add_all([rr_pending_web, rr_pending_transfer])
        session.commit()
        session.refresh(rr_pending_web)
        session.refresh(rr_pending_transfer)

        # A few already resolved historically, via the real resolver (so
        # they leave proper Transaction rows and admin cash-float balances).
        rr_history = [
            RechargeRequest(
                user_id=carla.id, username=carla.username, amount=10.0,
                method=RechargeMethod.CASH, target_telegram_admin_id=ta_ana.id,
                status=RechargeRequestStatus.PENDING,
            ),
            RechargeRequest(
                user_id=bruno.id, username=bruno.username, amount=25.0,
                method=RechargeMethod.CASH, target_telegram_admin_id=ta_leo.id,
                status=RechargeRequestStatus.PENDING,
            ),
            RechargeRequest(
                user_id=diego.id, username=diego.username, amount=30.0,
                method=RechargeMethod.TRANSFER, target_telegram_admin_id=ta_leo.id,
                status=RechargeRequestStatus.PENDING,
            ),
            RechargeRequest(
                user_id=alice.id, username=alice.username, amount=5.0,
                method=RechargeMethod.CASH, target_telegram_admin_id=ta_ana.id,
                status=RechargeRequestStatus.PENDING,
            ),
        ]
        session.add_all(rr_history)
        session.commit()
        for r in rr_history:
            session.refresh(r)

        recharge_request_resolver.resolve(
            str(rr_history[0].id), True, str(admin_ana.id), ActorType.ADMIN, "admin_ana", session,
        )
        recharge_request_resolver.resolve(
            str(rr_history[1].id), True, str(admin_leo.id), ActorType.ADMIN, "admin_leo", session,
        )
        recharge_request_resolver.resolve(
            str(rr_history[2].id), True, str(admin_leo.id), ActorType.ADMIN, "admin_leo", session,
        )
        recharge_request_resolver.resolve(
            str(rr_history[3].id), False, str(admin_ana.id), ActorType.ADMIN, "admin_ana", session,
        )

        # Settle admin_ana's float already (so Collections shows one admin
        # outstanding and one already collected — realistic mixed state).
        collection_service.collect_from_admin(str(superadmin.id), str(admin_ana.id), session)

        # ─── Refund requests ────────────────────────────────────────────
        # Pending, user-initiated.
        session.add(RefundRequest(
            user_id=alice.id, print_job_id=job_alice_1.id,
            message="Printer jammed halfway through, pages were unreadable",
        ))
        # Resolved normally (approved) — credit via the same path the API route uses.
        refund_bruno = refund_service.create_refund_request(
            str(bruno.id), str(job_bruno_1.id),
            RefundRequestCreate(message="Wrong file printed"),
            session,
        )
        result = UserService().adjust_balance(str(bruno.id), job_bruno_1.cost, session, enforce_credit_limit=False)
        session.add(Transaction(
            user_id=bruno.id, type=TransactionType.REFUND, amount=job_bruno_1.cost,
            balance_after=result.new_balance, actor_id=admin_ana.id, actor_type=ActorType.ADMIN,
            target_user_id=bruno.id, related_refund_request_id=refund_bruno.id, related_job_id=job_bruno_1.id,
            note="Refund approved by admin_ana",
        ))
        refund_bruno.status = RefundStatus.APPROVED
        refund_bruno.resolved_by_username = "admin_ana"
        session.add(refund_bruno)
        session.commit()

        # Admin-override refund (unsolicited) on Diego's job.
        refund_diego = refund_service.create_override_refund_request(
            str(diego.id), str(job_diego_1.id), str(admin_leo.id),
            "Print quality was unacceptable, refunding as a courtesy", "admin_leo", session,
        )
        result = UserService().adjust_balance(str(diego.id), job_diego_1.cost, session, enforce_credit_limit=False)
        session.add(Transaction(
            user_id=diego.id, type=TransactionType.REFUND, amount=job_diego_1.cost,
            balance_after=result.new_balance, actor_id=admin_leo.id, actor_type=ActorType.ADMIN,
            target_user_id=diego.id, related_refund_request_id=refund_diego.id, related_job_id=job_diego_1.id,
            note="Refund override by admin_leo",
        ))
        session.commit()

        # ─── Inventory ──────────────────────────────────────────────────
        inventory_service.create_item(
            "A4 Paper", InventoryCategory.PAPER, "sheets", 500, session,
            initial_stock=3000, reorder_supplier="OfficeSupplyCo",
        )
        inventory_service.create_item(
            "Toner B&W - OfficeJet", InventoryCategory.TONER_BW, "cartridges", 1, session,
            initial_stock=2, printer_id=str(printer_bw.id),
        )
        inventory_service.create_item(
            "Toner Color - LaserColor", InventoryCategory.TONER_COLOR, "cartridges", 1, session,
            initial_stock=0, printer_id=str(printer_color.id),
        )
        binding_supply = inventory_service.create_item(
            "Spiral Binding Coils", InventoryCategory.BINDING_SUPPLY, "units", 10, session,
            initial_stock=40,
        )

        # ─── Expenses ───────────────────────────────────────────────────
        expense_service.create_expense(
            ExpenseCategory.PAPER, 45.00, "Bulk A4 paper restock (5 reams)", str(admin_ana.id), session,
        )
        expense_service.create_expense(
            ExpenseCategory.TONER, 89.90, "Replacement color toner cartridge", str(admin_leo.id), session,
        )
        expense_service.create_expense(
            ExpenseCategory.MAINTENANCE, 30.00, "Printer service call - Common Room", str(admin_ana.id), session,
        )

        # ─── Products (Spiral Binding is seeded by the e8f9a0b1c2d3 migration;
        # re-create it here if a previous run of this script wiped it, then
        # link it to its inventory item) ──────────────────────────────────
        stmt = select(Product).where(Product.name == "Spiral Binding")
        spiral = session.exec(stmt).first()
        if spiral is None:
            spiral = Product(name="Spiral Binding", price=1.00, is_active=True)
            session.add(spiral)
            session.commit()
            session.refresh(spiral)
        spiral.inventory_item_id = binding_supply.id
        session.add(spiral)
        session.commit()

        session.commit()

    print("Seed complete.")
    print(f"All seeded human accounts share the password: {PWD}")
    print("  super_admin : superadmin")
    print("  admin       : admin_ana, admin_leo")
    print("  users       : alice_p, bruno_g, carla_m, diego_s, elena_r, fabio_t")


if __name__ == "__main__":
    main()
