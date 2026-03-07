import cups

from .logger import logger
from ..db.models.printerjob import JobStatus


class CUPSManager:
    def __init__(self):
        try: 
            self.conn = cups.Connection()
        except:
            logger.error("Failed to connect to CUPS")
            self.conn = None

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
        
    def get_job_status(self, cups_id: int) -> JobStatus | None:
        if self.conn is None:
            return None

        try:
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
