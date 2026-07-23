from sqlmodel import Session, select
import uuid

from ..models.refund_request import RefundRequest, RefundStatus
from ...schemas.refund import RefundRequestCreate, RefundRequestAdminUpdate


class RefundRequestService:

    ########################## CREATE #########################

    def create_refund_request(
        self,
        user_id: str,
        print_job_id: str,
        data: RefundRequestCreate,
        session: Session
    ) -> RefundRequest:
        refund = RefundRequest(
            user_id=uuid.UUID(user_id),
            print_job_id=uuid.UUID(print_job_id),
            message=data.message
        )
        session.add(refund)
        session.commit()
        session.refresh(refund)
        return refund

    def create_override_refund_request(
        self,
        user_id: str,
        print_job_id: str,
        admin_id: str,
        reason: str,
        admin_username: str,
        session: Session,
    ) -> RefundRequest:
        """An admin refunding a job the user never requested a refund
        for — created already-resolved, unlike the normal PENDING ->
        APPROVED flow. `initiated_by_admin_id` is what distinguishes this
        from an ordinary admin-approved request."""
        refund = RefundRequest(
            user_id=uuid.UUID(user_id),
            print_job_id=uuid.UUID(print_job_id),
            status=RefundStatus.APPROVED,
            initiated_by_admin_id=uuid.UUID(admin_id),
            admin_message=reason,
            resolved_by_username=admin_username,
        )
        session.add(refund)
        session.commit()
        session.refresh(refund)
        return refund

    ########################## READ #########################

    def get_refund_by_id(
        self,
        refund_id: str,
        session: Session
    ) -> RefundRequest | None:
        stmt = select(RefundRequest).where(RefundRequest.id == uuid.UUID(refund_id))
        return session.exec(stmt).first()

    def get_refund_by_job_id(
        self,
        print_job_id: str,
        session: Session
    ) -> RefundRequest | None:
        stmt = select(RefundRequest).where(RefundRequest.print_job_id == uuid.UUID(print_job_id))
        return session.exec(stmt).first()

    def get_refunds_by_user(
        self,
        user_id: str,
        session: Session,
        limit: int = 50,
        offset: int = 0
    ) -> list[RefundRequest]:
        stmt = (
            select(RefundRequest)
            .where(RefundRequest.user_id == uuid.UUID(user_id))
            .order_by(RefundRequest.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(stmt).all())

    def get_all_refunds(
        self,
        session: Session,
        limit: int = 50,
        offset: int = 0
    ) -> list[RefundRequest]:
        stmt = (
            select(RefundRequest)
            .order_by(RefundRequest.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(stmt).all())

    def get_pending_refunds(
        self,
        session: Session,
        limit: int = 50,
        offset: int = 0
    ) -> list[RefundRequest]:
        stmt = (
            select(RefundRequest)
            .where(RefundRequest.status == RefundStatus.PENDING)
            .order_by(RefundRequest.created_at.asc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(stmt).all())

    ########################## UPDATE #########################

    def update_refund_request(
        self,
        refund_id: str,
        data: RefundRequestAdminUpdate,
        session: Session,
        resolved_by_username: str | None = None
    ) -> RefundRequest | None:
        refund = self.get_refund_by_id(refund_id, session)
        if refund is None:
            return None

        refund.status = data.status
        if data.admin_message is not None:
            refund.admin_message = data.admin_message
        if resolved_by_username is not None:
            refund.resolved_by_username = resolved_by_username

        session.add(refund)
        session.commit()
        session.refresh(refund)
        return refund

    def delete_refund_request(
        self,
        refund_id: str,
        session: Session
    ) -> bool:
        refund = self.get_refund_by_id(refund_id, session)
        if refund is None:
            return False
        session.delete(refund)
        session.commit()
        return True
