from pydantic import BaseModel
from datetime import datetime
import uuid

from ..db.models.file import File
from ..db.models.printer import Printer
from ..db.models.printerjob import JobStatus

from .print import PrintOptions


class PrintJobCreate(BaseModel):
    user_id: str
    printer: Printer
    file: File
    print_options: PrintOptions
    pages: int
    cost: float

    @property
    def dump_on_DB(self) -> dict:
        from .print import SidesOption
        return {
            "user_id": uuid.UUID(self.user_id),
            "printer_id": self.printer.id,
            "printer_name": self.printer.name,
            "file_id": self.file.id,
            "file_name": self.file.filename,
            "file_size": self.file.size_bytes,
            "pages": self.pages,
            "number_up": self.print_options.number_up,
            "two_sided": self.print_options.sides != SidesOption.ONE_SIDED,
            "color": self.print_options.color,
            "cost": self.cost
        }


class PrintJobRead(BaseModel):
    id: uuid.UUID
    printer_name: str
    file_name: str
    pages: int
    number_up: int
    two_sided: bool
    color: bool
    cost: float
    status: JobStatus
    created_at: datetime
    completed_at: datetime | None = None


class PrintJobAdminRead(PrintJobRead):
    user_id: uuid.UUID
