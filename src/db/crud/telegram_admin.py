from sqlmodel import Session, select
import uuid

from ..models.telegram_admin import TelegramAdmin


class TelegramAdminService:

    def create_telegram_admin(
        self,
        user_id: str,
        telegram_id: str,
        session: Session
    ):
        
        ta = TelegramAdmin(
            user_id=uuid.UUID(user_id),
            telegram_id=telegram_id
        )

        session.add(ta)
        session.commit()

        return ta
    
    def get_telegram_admin(
        self,
        telegram_id: str,
        session: Session
    ):
        stmt = select(TelegramAdmin).where(TelegramAdmin.telegram_id == telegram_id)
        ta = session.exec(stmt).first()

        if ta is None:
            return None
        
        return ta

    
    def get_all(
        self,
        session: Session
    ):
        stmt = select(TelegramAdmin)
        return session.exec(stmt).all()

    def delete_telegram_admin(
        self,
        user_id: str,
        session: Session
    ):
        stmt = select(TelegramAdmin).where(TelegramAdmin.user_id == user_id)
        ta = session.exec(stmt).first()

        if ta is None:
            return None
        
        session.delete(ta)
        session.commit()

        return ta

    def delete_by_id(
        self,
        ta_id: str,
        session: Session
    ):
        import uuid as _uuid
        stmt = select(TelegramAdmin).where(TelegramAdmin.id == _uuid.UUID(ta_id))
        ta = session.exec(stmt).first()

        if ta is None:
            return None

        session.delete(ta)
        session.commit()

        return ta
