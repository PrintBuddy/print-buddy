from sqlmodel import Session, select

from ..models.printer import Printer
from ...schemas.printer import PrinterCreate, PrinterCUPSUpdate, PrinterAdminUpdate
from ...core.utils import generate_time


class PrinterService:


    ################### CREATE #######################

    def create_printer(
        self, 
        printer_data: PrinterCreate,
        session: Session
    ):
        
        printer = Printer(**printer_data.model_dump())
        session.add(printer)
        session.commit()

        return printer

    ##################### READ #########################
    
    def get_all_printers(self, session: Session):
        stmt = select(Printer)
        printers = session.exec(stmt).all()
        return printers

    def get_active_printers(self, session: Session):
        stmt = select(Printer).where(Printer.is_active == True)
        printers = session.exec(stmt).all()
        return printers
    
    def get_printer_by_name(
        self,
        name: str,
        session: Session
    ):
        stmt = select(Printer).where(Printer.name == name)
        printer = session.exec(stmt).first()
        
        return printer
    
    def calculate_cost(
        self,
        printer_name: str,
        pages: int,
        color: bool,
        session: Session
    ):
        pass
    
    ##################### UPDATE #########################

    def update_printer_CUPS(
        self,
        printer_update: PrinterCUPSUpdate,
        session: Session
    ):
        name = printer_update.name
        stmt = select(Printer).where(Printer.name == name)
        printer = session.exec(stmt).first()

        if printer is None:
            new_printer = PrinterCreate(**printer_update.model_dump())
            return self.create_printer(new_printer, session)

        printer.location = printer_update.location
        printer.status = printer_update.status
        printer.state_reasons = printer_update.state_reasons
        printer.supports_duplex = printer_update.supports_duplex
        printer.updated_at = generate_time()

        session.commit()
        return printer
    
    def update_printer_admin(
        self,
        name: str,
        printer_data: PrinterAdminUpdate,
        session: Session
    ):
        
        stmt = select(Printer).where(Printer.name == name)
        printer = session.exec(stmt).first()

        if printer is None:
            return None
        
        data = printer_data.model_dump(exclude_none=True)
        for key, val in data.items():
            setattr(printer, key, val)

        session.commit()
        return printer

    ##################### DELETE #########################

    def delete_printer(
        self,
        name: str,
        session: Session
    ):
        
        stmt = select(Printer).where(Printer.name == name)
        printer = session.exec(stmt).first()

        if printer is None:
            return None
        
        session.delete(printer)
        session.commit()

        return printer