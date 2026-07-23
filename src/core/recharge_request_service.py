from dataclasses import dataclass
from typing import Literal

from sqlmodel import Session

from ..db.crud.recharge_request import RechargeRequestService
from ..db.models.recharge_request import RechargeRequest, RechargeRequestStatus
from ..db.models.transaction import ActorType
from .ledger_service import LedgerService

recharge_request_service = RechargeRequestService()
ledger_service = LedgerService()


@dataclass
class RechargeResolveResult:
    ok: bool
    reason: Literal["not_found", "already_resolved", "user_not_found"] | None
    request: RechargeRequest | None


class RechargeRequestResolver:
    """The one place a recharge request actually gets approved/rejected —
    used by both the web (JWT admin) route and the Telegram (bot-secret)
    route, so there is exactly one place the balance-credit + status
    transition happens, not two copies of it."""

    def resolve(
        self,
        request_id: str,
        approve: bool,
        actor_id: str,
        actor_type: ActorType,
        resolved_by_username: str,
        session: Session,
    ) -> RechargeResolveResult:
        request = recharge_request_service.get_for_resolve(request_id, session)
        if request is None:
            return RechargeResolveResult(False, "not_found", None)

        if request.status != RechargeRequestStatus.PENDING:
            return RechargeResolveResult(False, "already_resolved", request)

        if approve:
            entry_note = f"Recharge request approved by {resolved_by_username}"
            result = ledger_service.record_recharge(
                str(request.user_id), request.amount, actor_id, actor_type, session,
                note=entry_note,
                related_recharge_request_id=str(request.id),
                enforce_credit_limit=False,
            )
            if not result.ok:
                return RechargeResolveResult(False, "user_not_found", request)
            request.status = RechargeRequestStatus.APPROVED
        else:
            request.status = RechargeRequestStatus.REJECTED

        request.resolved_by_username = resolved_by_username
        session.add(request)
        session.commit()
        session.refresh(request)

        return RechargeResolveResult(True, None, request)


recharge_request_resolver = RechargeRequestResolver()
