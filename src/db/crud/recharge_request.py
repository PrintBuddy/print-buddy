import uuid

from sqlmodel import Session, select

from ..models.recharge_request import RechargeRequest
from ...schemas.telegram import TelegramRechargeRequestCreate


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

    def get_recharge_request_by_id(
        self,
        request_id: str,
        session: Session,
    ) -> RechargeRequest | None:
        stmt = select(RechargeRequest).where(RechargeRequest.id == uuid.UUID(request_id))
        return session.exec(stmt).first()
