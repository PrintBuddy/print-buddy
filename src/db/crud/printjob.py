from sqlmodel import Session, select, or_

from ...db.models.printerjob import PrintJob, JobStatus, TRANSIT_STATUS, ERROR_STATUS
from ...schemas.printjob import PrintJobCreate
from ...core.utils import generate_time

from .user import UserService


user_service = UserService()


class PrintJobService:

    ########################## CREATE #########################

    def create_job(
        self,
        cups_id: str,
        printjob: PrintJobCreate,
        session: Session,
    ) -> PrintJob:
        
        new_printjob = PrintJob(
            cups_id=cups_id,
            **printjob.dump_on_DB
        )

        session.add(new_printjob)
        session.commit()

        return new_printjob
    

    ########################## READ #########################

    def get_jobs_by_id(
        self,
        user_id: str,
        session: Session,
        limit: int = 50,
        offset: int = 0
    ):
        stmt = (
            select(PrintJob)
            .where(PrintJob.user_id == user_id)
            .order_by(PrintJob.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        jobs = session.exec(stmt).all()

        return jobs

    def get_job_by_id(
        self,
        job_id: str,
        session: Session
    ) -> PrintJob | None:
        stmt = select(PrintJob).where(PrintJob.id == job_id)
        return session.exec(stmt).first()

    def get_all_jobs(
        self,
        session: Session,
        limit: int = 50,
        offset: int = 0
    ) -> list[PrintJob]:
        stmt = (
            select(PrintJob)
            .order_by(PrintJob.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(stmt).all())

    def get_transitory_status_jobs(
        self,
        session: Session
    ):
        
        conditions = [PrintJob.status == value for value in TRANSIT_STATUS]
        stmt = select(PrintJob.id, PrintJob.cups_id, PrintJob.status).where(
            or_(*conditions)
        )
        jobs = session.exec(stmt).all()

        return jobs
    

    ########################## UPDATE #########################

    def update_job_status(
        self,
        job_id: str,
        new_status: JobStatus,
        session: Session
    ) -> PrintJob | None:
        
        stmt = select(PrintJob).where(PrintJob.id == job_id)
        job = session.exec(stmt).first()

        if job is None:
            return job

        job.status = new_status

        if new_status not in TRANSIT_STATUS:
            job.completed_at = generate_time()

        session.commit()

        return job
