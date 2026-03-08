import cups
import threading

from .logger import logger
from ..db.models.printerjob import JobStatus


class CUPSManager:
    def __init__(self):
        try: 
            self.conn = cups.Connection()
        except:
            logger.error("Failed to connect to CUPS")
            self.conn = None

        # pycups / libcups is not thread-safe: serialise all calls.
        self._lock = threading.Lock()

        self.CUPS_STATE_MAP = {
            3: "idle",
            4: "printing",
            5: "stopped"
        }

        self.JOB_STATE_MAP = {
            3: JobStatus.PENDING,
            4: JobStatus.HELD,
            5: JobStatus.PRINTING,
            6: JobStatus.STOPPED,
            7: JobStatus.CANCELLED,
            8: JobStatus.ABORTED,
            9: JobStatus.COMPLETED
        }

        self.MAX_TRIES = 3
        self.jobs_with_error = {}

    def get_printers(self) -> list[dict]:
        """
        Returns CUPS printers info on a list of dictionaries
        """
        if self.conn is None:
            return []

        try:
            with self._lock:
                printers = self.conn.getPrinters()
        except cups.IPPError:
            logger.error("CUPS Error, unable to retrieve printers")
            return []
        
        result = []
        for name, attrs in printers.items():
            raw_reasons = attrs.get("printer-state-reasons", [])
            # "none" is CUPS's default value meaning no issues — discard it
            state_reasons = [r for r in raw_reasons if r != "none"]
            result.append({
                "name": name,
                "location": attrs.get("printer-location"),
                "status": self.CUPS_STATE_MAP.get(attrs.get("printer-state"), "unknown"),
                "state_reasons": state_reasons,
            })
        
        return result

    def print_file(
        self,
        printer_name: str,
        file_path: str,
        title:str,
        options: dict
    ) -> str:
        
        if self.conn is None:
            return ""
        
        try:
            with self._lock:
                job_id = self.conn.printFile(
                    printer=printer_name,
                    filename=file_path,
                    title=title,
                    options=options
                )
            return str(job_id)
        
        except cups.IPPError:
            return ""
        
        except Exception as e:
            print(e)
            return ""
        
    def get_toner_levels(self, printer_name: str) -> list[dict] | None:
        """
        Returns toner/ink marker levels for the given CUPS printer.
        Returns None if CUPS is unavailable or the printer is not found.
        Returns an empty list if the printer does not report marker info.
        Each entry: {name, color, level, low_level, high_level}
        level == -1 means the driver cannot report a value for that slot.
        """
        if self.conn is None:
            return None

        try:
            with self._lock:
                attrs = self.conn.getPrinterAttributes(printer_name)
        except cups.IPPError:
            return None

        try:
            levels = attrs.get("marker-levels")
            names = attrs.get("marker-names")
            colors = attrs.get("marker-colors")
            low = attrs.get("marker-low-levels")
            high = attrs.get("marker-high-levels")

            if levels is None or names is None:
                return []

            def to_list(v):
                return v if isinstance(v, list) else [v]

            def safe_int(v, default):
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return default

            levels = [safe_int(x, -1) for x in to_list(levels)]
            names = [str(x) for x in to_list(names)]
            colors = (
                [str(x) if x is not None else None for x in to_list(colors)]
                if colors is not None
                else [None] * len(names)
            )
            low = (
                [safe_int(x, 10) for x in to_list(low)]
                if low is not None
                else [10] * len(names)
            )
            high = (
                [safe_int(x, 100) for x in to_list(high)]
                if high is not None
                else [100] * len(names)
            )

            n = len(names)
            if n == 0:
                return []

            # Some drivers prepend internal/waste-toner slots that are not named;
            # align from the end so the named markers match correctly.
            if len(levels) > n:
                levels = levels[-n:]
            if len(low) > n:
                low = low[-n:]
            if len(high) > n:
                high = high[-n:]
            if len(colors) > n:
                colors = colors[-n:]

            return [
                {
                    "name": names[i],
                    "color": colors[i] if i < len(colors) else None,
                    "level": levels[i] if i < len(levels) else -1,
                    "low_level": low[i] if i < len(low) else 10,
                    "high_level": high[i] if i < len(high) else 100,
                }
                for i in range(n)
            ]
        except Exception:
            logger.error(f"Unexpected error parsing toner levels for {printer_name}")
            return []

    def get_job_status(self, cups_id: int) -> JobStatus | None:
        if self.conn is None:
            return None

        try:
            with self._lock:
                attrs = self.conn.getJobAttributes(cups_id)
        except cups.IPPError as e:
            
            if not cups_id in self.jobs_with_error:
                self.jobs_with_error[cups_id] = 0
            self.jobs_with_error[cups_id] += 1

            if self.jobs_with_error[cups_id] > self.MAX_TRIES:
                self.jobs_with_error.pop(cups_id)
                return JobStatus.ABORTED
            
            return None

        cups_state = attrs["job-state"]

        return self.JOB_STATE_MAP[cups_state]
