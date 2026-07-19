import uuid

from sqlmodel import Session

from ..db.crud.user import UserService, BalanceUpdateResult
from ..db.crud.transaction import TransactionService
from ..db.models.transaction import TransactionType, ActorType
from ..schemas.transaction import TransactionCreate
from .utils import round_money

user_service = UserService()
tx_service = TransactionService()


class LedgerService:
    """Single choke point for admin-authorized balance changes (recharge /
    adjustment), used by both the web-admin routes and the Telegram-admin
    routes. Before this existed, each of those four call sites duplicated
    the adjust_balance -> build TransactionCreate -> create_transaction
    sequence independently."""

    def record_recharge(
        self,
        user_id: str,
        amount: float,
        actor_id: str | None,
        actor_type: ActorType,
        session: Session,
        *,
        note: str | None = None,
        related_recharge_request_id: str | None = None,
        enforce_credit_limit: bool = False,
    ) -> BalanceUpdateResult:
        amount = round_money(amount)

        result = user_service.adjust_balance(
            user_id, amount, session, enforce_credit_limit=enforce_credit_limit
        )
        if not result.ok:
            return result

        tx_data = TransactionCreate(
            user_id=uuid.UUID(user_id),
            type=TransactionType.RECHARGE,
            amount=amount,
            balance_after=result.new_balance,  # type: ignore
            note=note,
            actor_id=uuid.UUID(actor_id) if actor_id else None,
            actor_type=actor_type,
            target_user_id=uuid.UUID(user_id),
            related_recharge_request_id=(
                uuid.UUID(related_recharge_request_id) if related_recharge_request_id else None
            ),
        )
        tx_service.create_transaction(tx_data, session)

        return result

    def record_adjustment(
        self,
        user_id: str,
        target_balance: float,
        actor_id: str | None,
        actor_type: ActorType,
        session: Session,
        *,
        note: str | None = None,
        current_balance: float | None = None,
    ) -> BalanceUpdateResult:
        if current_balance is None:
            current_balance = user_service.get_user_balance(user_id, session)
            if current_balance is None:
                return BalanceUpdateResult(False, "not_found", None)

        diff = round_money(round_money(target_balance) - round_money(current_balance))

        result = user_service.adjust_balance(
            user_id, diff, session, enforce_credit_limit=True
        )
        if not result.ok:
            return result

        tx_data = TransactionCreate(
            user_id=uuid.UUID(user_id),
            type=TransactionType.ADJUSTMENT,
            amount=diff,
            balance_after=result.new_balance,  # type: ignore
            note=note,
            actor_id=uuid.UUID(actor_id) if actor_id else None,
            actor_type=actor_type,
            target_user_id=uuid.UUID(user_id),
        )
        tx_service.create_transaction(tx_data, session)

        return result
