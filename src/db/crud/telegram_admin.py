from sqlmodel import Session, select
import uuid

from ..models.telegram_admin import TelegramAdmin
from ..models.user import User


class TelegramAdminService:

    def create_telegram_admin(
        self,
        user_id: str,
        telegram_id: str,
        session: Session,
        *,
        phone_number: str | None = None,
        accepts_transfer: bool = False,
        bank_name: str | None = None,
        bank_iban: str | None = None,
        bank_link: str | None = None,
    ):

        ta = TelegramAdmin(
            user_id=uuid.UUID(user_id),
            telegram_id=telegram_id,
            phone_number=phone_number,
            accepts_transfer=accepts_transfer,
            bank_name=bank_name,
            bank_iban=bank_iban,
            bank_link=bank_link,
        )

        session.add(ta)
        session.commit()

        return ta

    def update_telegram_admin(
        self,
        ta_id: str,
        session: Session,
        *,
        telegram_id: str | None = None,
        phone_number: str | None = None,
        accepts_transfer: bool | None = None,
        bank_name: str | None = None,
        bank_iban: str | None = None,
        bank_link: str | None = None,
    ) -> TelegramAdmin | None:
        ta = self.get_by_id(ta_id, session)
        if ta is None:
            return None

        if telegram_id is not None:
            ta.telegram_id = telegram_id
        if phone_number is not None:
            ta.phone_number = phone_number
        if accepts_transfer is not None:
            ta.accepts_transfer = accepts_transfer
        if bank_name is not None:
            ta.bank_name = bank_name
        if bank_iban is not None:
            ta.bank_iban = bank_iban
        if bank_link is not None:
            ta.bank_link = bank_link

        session.add(ta)
        session.commit()
        session.refresh(ta)
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
        session: Session,
        limit: int = 50,
        offset: int = 0
    ):
        stmt = (
            select(TelegramAdmin)
            .order_by(TelegramAdmin.created_at.desc())  # type: ignore
            .limit(limit)
            .offset(offset)
        )
        return session.exec(stmt).all()

    def get_all_chat_ids(
        self,
        session: Session
    ) -> list[str]:
        stmt = select(TelegramAdmin.telegram_id)
        return list(session.exec(stmt).all())

    def get_eligible_admins(
        self,
        session: Session
    ) -> list[tuple[TelegramAdmin, User]]:
        """Every TelegramAdmin paired with its User row, for the "who did
        you pay" picker — deliberately joined here (not just a bare
        TelegramAdmin list) so the caller never has to look up chat_id and
        display name separately."""
        stmt = select(TelegramAdmin, User).join(User, TelegramAdmin.user_id == User.id)
        return list(session.exec(stmt).all())

    def get_by_id(
        self,
        ta_id: str,
        session: Session
    ) -> TelegramAdmin | None:
        stmt = select(TelegramAdmin).where(TelegramAdmin.id == uuid.UUID(ta_id))
        return session.exec(stmt).first()

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
