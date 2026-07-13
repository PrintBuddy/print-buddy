from sqlmodel import Session, select
from ..db.main import engine
from .scheduler import scheduler
import cups


def check_cups() -> dict:
    """Check connection to CUPS and list available printers."""
    try:
        conn = cups.Connection()  # usa CUPS_SERVER (socket o hostname)
        printers = conn.getPrinters()

        if printers:
            return {"status": "ok", "printers": list(printers.keys())}
        else:
            return {"status": "ok", "printers": [], "message": "No printers available"}

    except RuntimeError as e:
        return {"status": "error", "message": f"Failed to connect to CUPS: {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_database() -> dict:
    """Verify database connection and query execution."""
    try:
        with Session(engine) as session:
            session.exec(select(1)).first()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_scheduler() -> dict:
    """Check if the scheduler is running and list active jobs."""
    try:
        return scheduler.get_status()
    except Exception as e:
        return {"status": "error", "message": str(e)}


def run_healthcheck() -> dict:
    """Run a complete system health check."""
    return {
        "cups": check_cups(),
        "database": check_database(),
        "scheduler": check_scheduler(),
    }

