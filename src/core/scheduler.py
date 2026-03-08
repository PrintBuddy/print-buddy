from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from .cups_manager import CUPSManager
from ..db.main import engine

from ..db.crud.printer import PrinterService
from ..db.crud.printjob import PrintJobService
from ..db.crud.user import UserService
from ..db.crud.transaction import TransactionService
from ..db.crud.file import FileService
from ..db.crud.app_config import AppConfigService

from ..db.models.printerjob import ERROR_STATUS
from ..db.models.transaction import TransactionType
from ..schemas.printer import PrinterCUPSUpdate
from ..schemas.transaction import TransactionCreate

from ..core.utils import generate_time
from ..core.file_manager import FileManager
from ..core.mail_assistant import send_toner_alert_email
from .logger import logger


TONER_ALERT_CONFIG_KEY = "toner_alert_config"
TONER_ALERT_STATE_KEY = "toner_alert_state"
TONER_ALERT_DEFAULT_CONFIG = {"enabled": False, "interval_hours": 24}

printer_service = PrinterService()
pj_service = PrintJobService()
user_service = UserService()
tx_service = TransactionService()
file_service = FileService()
config_service = AppConfigService()
fm = FileManager()

cups_mgr = CUPSManager()


class Scheduler(AsyncIOScheduler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.printers_data = []

    @staticmethod
    def run_in_executor(sync_func):
        """Decorator to execute sync methods in a thread executor."""
        async def wrapper(self, *args, **kwargs):
            try:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, lambda: sync_func(self, *args, **kwargs))
            except asyncio.CancelledError:
                logger.warning(f"SCHEDULER: Process {sync_func.__name__} cancelled during shutdown")
                return None
            except Exception as e:
                logger.warning(f"SCHEDULER: Process {sync_func.__name__} stopped due to error: {e}")

        return wrapper

    def get_status(self) -> dict:
        try:
            if not self.running:
                return {"status": "error", "message": "Scheduler not running"}

            jobs = []
            for job in self.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
                })

            if not jobs:
                return {"status": "warning", "message": "No jobs registered"}

            return {"status": "ok", "jobs": jobs}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _normalize_data(self, printers_data: list[dict]) -> str:
        return json.dumps(printers_data, sort_keys=True)

    def check_printer_changes(self, printers_data: list[dict]) -> bool:
        if not self.printers_data:
            self.printers_data = printers_data
            return True

        old_state = self._normalize_data(self.printers_data)
        new_state = self._normalize_data(printers_data)

        if old_state != new_state:
            self.printers_data = printers_data
            return True

        return False

    def update_printers_sync(self):
        printers_data = cups_mgr.get_printers()

        if not self.check_printer_changes(printers_data):
            return

        with Session(engine) as session:
            for data in printers_data:

                print_update = PrinterCUPSUpdate(**data)

                logger.info(f"SCHEDULER: Changing state of printer {print_update.name} to {print_update.status}")
                printer_service.update_printer_CUPS(
                    printer_update=print_update,
                    session=session
                )

    def update_jobs_sync(self):

        with Session(engine) as session:
            jobs_to_update = pj_service.get_transitory_status_jobs(session)
        
            if not jobs_to_update:
                return
            
            for job_id, cups_id, status in jobs_to_update:
                new_status = cups_mgr.get_job_status(int(cups_id))
                
                if new_status is None:
                    continue

                if status != new_status:
                    job = pj_service.update_job_status(str(job_id), new_status, session)
                    if job is not None and new_status in ERROR_STATUS:
                        user_service.add_credit(str(job.user_id), job.cost, session)

                        balance = user_service.get_user_balance(str(job.user_id), session)

                        tx_data = TransactionCreate(
                            user_id=job.user_id,
                            type=TransactionType.REFUND,
                            amount=job.cost,
                            balance_after=balance,  # type: ignore
                            note=f"Refunded from file print: {job.file_name}"
                        )

                        tx_service.create_transaction(tx_data, session)
                        logger.info(f"SCHEDULER: Refunded user {job.user_id} the amount of {job.cost}")

    def check_toner_alerts_sync(self) -> tuple[list[dict], list[str]] | None:
        """
        Checks toner levels across all printers and determines if any alert emails
        need to be sent. Returns (alerts, admin_emails) or None if disabled.
        Updates the persisted notification state.
        """
        with Session(engine) as session:
            raw_config = config_service.get(TONER_ALERT_CONFIG_KEY, session) or TONER_ALERT_DEFAULT_CONFIG
            enabled = raw_config.get("enabled", False)
            if not enabled:
                return None

            interval_hours = max(1, raw_config.get("interval_hours", 24))
            raw_state = config_service.get(TONER_ALERT_STATE_KEY, session) or {}
            printers = printer_service.get_all_printers(session)
            printer_names = [p.name for p in printers]
            admin_emails = user_service.get_admin_emails(session)

        if not admin_emails:
            logger.warning("SCHEDULER: Toner alert enabled but no admin emails found")
            return None

        alerts: list[dict] = []
        new_state: dict = {}
        now = generate_time()

        for name in printer_names:
            markers = cups_mgr.get_toner_levels(name)
            if not markers:
                continue

            low_markers = [
                m for m in markers
                if m["level"] != -1 and m["level"] < m["low_level"]
            ]

            if not low_markers:
                # Toner is fine — do not carry state forward so next dip re-notifies
                continue

            printer_state = raw_state.get(name, {})
            last_notified_str = printer_state.get("last_notified")

            should_notify = False
            if last_notified_str is None:
                should_notify = True
            else:
                try:
                    last_notified = datetime.fromisoformat(last_notified_str)
                    elapsed_hours = (now - last_notified).total_seconds() / 3600
                    should_notify = elapsed_hours >= interval_hours
                except (ValueError, TypeError):
                    should_notify = True

            new_state[name] = {
                "last_notified": now.isoformat() if should_notify else last_notified_str,
                "markers": [m["name"] for m in low_markers],
            }

            if should_notify:
                alerts.append({"printer_name": name, "markers": low_markers})

        with Session(engine) as session:
            config_service.set(TONER_ALERT_STATE_KEY, new_state, session)

        return alerts, admin_emails

    async def check_toner_alerts(self):
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self.check_toner_alerts_sync)

            if not result:
                return

            alerts, admin_emails = result
            if not alerts:
                return

            await send_toner_alert_email(admin_emails, alerts)
            logger.info(f"SCHEDULER: Sent toner low alert for {len(alerts)} printer(s)")

        except asyncio.CancelledError:
            logger.warning("SCHEDULER: check_toner_alerts cancelled during shutdown")
        except Exception as e:
            logger.error(f"SCHEDULER: check_toner_alerts error: {e}")

    def delete_old_files_sync(self):
        timeframe = generate_time() - timedelta(days=1)

        with Session(engine) as session:
            old_files = file_service.get_old_files(
                timeframe, session
            )

            for file in old_files:
                file_id = file.id
                file_service.delete_file(str(file_id), session)
                path = Path(file.filepath)
                fm.delete_file(path)
            
            if old_files:
                logger.info(f"SCHEDULER: Deleted {len(old_files)} old files from system")

    @run_in_executor
    def update_printers(self):
        return self.update_printers_sync()

    @run_in_executor
    def update_jobs(self):
        return self.update_jobs_sync()

    @run_in_executor
    def delete_old_files(self):
        return self.delete_old_files_sync()

    def start(self, *args, **kwargs):
        self.add_job(self.update_printers, "interval", seconds=60, name="printer_updater")
        self.add_job(self.update_jobs, "interval", seconds=5, name="jobs_updater")
        self.add_job(self.delete_old_files, "interval", seconds=7200, name="file_cleaner")
        self.add_job(self.check_toner_alerts, "interval", seconds=60, name="toner_alert_checker")
        
        super().start(*args, **kwargs)


scheduler = Scheduler()
