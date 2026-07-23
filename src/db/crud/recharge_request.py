import uuid

from sqlmodel import Session, select

from ..models.recharge_request import RechargeRequest, RechargeRequestStatus
from ..models.telegram_admin import TelegramAdmin
from ..models.user import User
from ...schemas.telegram import TelegramRechargeRequestCreate
from ...schemas.recharge_request import RechargeRequestCreate


class RechargeRequestService:
    def create_recharge_request(
        self,
        user_id: str,
        data: TelegramRechargeRequestCreate,
        session: Session,
    ) -> RechargeRequest:
        request = RechargeRequest(
            user_id=uuid.UUID(user_id),
            username=data.username,
            amount=data.amount,
            message=data.message,
            requester_chat_id=data.chat_id,
            requester_telegram_username=data.telegram_username,
            requester_first_name=data.telegram_first_name,
            requester_last_name=data.telegram_last_name,
        )
        session.add(request)
        session.commit()
        session.refresh(request)
        return request

    def create_web_request(
        self,
        user_id: str,
        username: str,
        data: RechargeRequestCreate,
        session: Session,
    ) -> RechargeRequest:
        request = RechargeRequest(
            user_id=uuid.UUID(user_id),
            username=username,
            amount=data.amount,
            message=data.message,
            method=data.method,
            target_telegram_admin_id=data.target_telegram_admin_id,
        )
        session.add(request)
        session.commit()
        session.refresh(request)
        return request

    def get_recharge_request_by_id(
        self,
        request_id: str,
        session: Session,
    ) -> RechargeRequest | None:
        stmt = select(RechargeRequest).where(RechargeRequest.id == uuid.UUID(request_id))
        return session.exec(stmt).first()

    def get_for_resolve(
        self,
        request_id: str,
        session: Session,
    ) -> RechargeRequest | None:
        """Row-locked fetch, so two concurrent resolve attempts (one via
        the web, one via Telegram) serialize instead of racing."""
        stmt = (
            select(RechargeRequest)
            .where(RechargeRequest.id == uuid.UUID(request_id))
            .with_for_update()
        )
        return session.exec(stmt).first()

    def get_by_user(
        self,
        user_id: str,
        session: Session,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RechargeRequest]:
        stmt = (
            select(RechargeRequest)
            .where(RechargeRequest.user_id == uuid.UUID(user_id))
            .order_by(RechargeRequest.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(stmt).all())

    def get_by_user_with_target_admin(
        self,
        user_id: str,
        session: Session,
        limit: int = 50,
        offset: int = 0,
    ) -> list[tuple[RechargeRequest, User | None]]:
        """Same as get_by_user, but also resolves who the request was sent
        to — outer-joined since target_telegram_admin_id is null for
        legacy bot-created rows."""
        stmt = (
            select(RechargeRequest, User)
            .outerjoin(TelegramAdmin, RechargeRequest.target_telegram_admin_id == TelegramAdmin.id)  # type: ignore
            .outerjoin(User, TelegramAdmin.user_id == User.id)  # type: ignore
            .where(RechargeRequest.user_id == uuid.UUID(user_id))
            .order_by(RechargeRequest.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(stmt).all())

    def get_pending(
        self,
        session: Session,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RechargeRequest]:
        stmt = (
            select(RechargeRequest)
            .where(RechargeRequest.status == RechargeRequestStatus.PENDING)
            .order_by(RechargeRequest.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(stmt).all())

    def get_all(
        self,
        session: Session,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RechargeRequest]:
        stmt = (
            select(RechargeRequest)
            .order_by(RechargeRequest.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(stmt).all())
