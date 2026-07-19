from fastapi import APIRouter, status, HTTPException

from ..dependencies.token import TokenDep, AdminTokenDep
from ..dependencies.database import SessionDep
from ..dependencies.pagination import PaginationDep

from ...schemas.recharge_request import (
    RechargeAdminOption,
    RechargeRequestCreate,
    RechargeRequestResolve,
    RechargeRequestRead,
    RechargeRequestAdminRead,
)
from ...db.crud.user import UserService
from ...db.crud.telegram_admin import TelegramAdminService
from ...db.crud.recharge_request import RechargeRequestService
from ...db.models.transaction import ActorType
from ...core.recharge_request_service import recharge_request_resolver
from ...core.telegram_notifier import telegram_notifier
from ...core.utils import round_money


router = APIRouter()

user_service = UserService()
ta_service = TelegramAdminService()
recharge_request_service = RechargeRequestService()


def _notification_text(user, amount: float, method: str, message: str | None) -> str:
    lines = [
        "🔔 <b>New Recharge Request</b>",
        "",
        f"👤 <b>User:</b> {user.name} {user.surname} (@{user.username})",
        f"💶 <b>Amount:</b> {amount:.2f}€",
        f"💳 <b>Method:</b> {method.capitalize()}",
        "🌐 <b>Submitted via the app</b>",
    ]
    if message:
        lines.append(f"📝 <b>Message:</b> {message}")
    return "\n".join(lines)


def _resolution_text(request, resolved_by: str) -> str:
    approved = request.status.value == "approved"
    header = "✅ <b>Recharge Request Approved</b>" if approved else "❌ <b>Recharge Request Rejected</b>"
    return (
        f"{header}\n\n"
        f"👤 <b>User:</b> {request.username}\n"
        f"💶 <b>Amount:</b> {round_money(request.amount):.2f}€\n"
        f"🛠️ <b>Handled by:</b> {resolved_by}"
    )


@router.get(
    "/admins",
    response_model=list[RechargeAdminOption],
    status_code=status.HTTP_200_OK,
)
def get_eligible_admins(
    token: TokenDep,
    session: SessionDep,
):
    """Who the "I paid admin X" picker offers — every configured Telegram
    admin, joined with their display info."""
    pairs = ta_service.get_eligible_admins(session)
    return [
        RechargeAdminOption(
            telegram_admin_id=ta.id,
            username=u.username,
            name=u.name,
            surname=u.surname,
        )
        for ta, u in pairs
    ]


@router.post(
    "",
    response_model=RechargeRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def create_recharge_request(
    data: RechargeRequestCreate,
    token: TokenDep,
    session: SessionDep,
):
    user_id = token.credentials
    user = user_service.get_user_by_id(user_id, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target_admin = ta_service.get_by_id(str(data.target_telegram_admin_id), session)
    if target_admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Selected admin not found")

    request = recharge_request_service.create_web_request(user_id, user.username, data, session)

    message_id = telegram_notifier.send_recharge_request_message(
        target_admin.telegram_id,
        _notification_text(user, round_money(data.amount), data.method.value, data.message),
        str(request.id),
    )
    if message_id is not None:
        request.notified_chat_id = target_admin.telegram_id
        request.notified_message_id = message_id
        session.add(request)
        session.commit()
        session.refresh(request)

    return request


@router.get(
    "/me",
    response_model=list[RechargeRequestRead],
    status_code=status.HTTP_200_OK,
)
def get_my_recharge_requests(
    token: TokenDep,
    session: SessionDep,
    pagination: PaginationDep,
):
    user_id = token.credentials
    return recharge_request_service.get_by_user(user_id, session, pagination.limit, pagination.offset)


@router.get(
    "/pending",
    response_model=list[RechargeRequestAdminRead],
    status_code=status.HTTP_200_OK,
)
def get_pending_recharge_requests(
    token: AdminTokenDep,
    session: SessionDep,
    pagination: PaginationDep,
):
    return recharge_request_service.get_pending(session, pagination.limit, pagination.offset)


@router.patch(
    "/{request_id}",
    response_model=RechargeRequestAdminRead,
    status_code=status.HTTP_200_OK,
)
def resolve_recharge_request(
    request_id: str,
    data: RechargeRequestResolve,
    token: AdminTokenDep,
    session: SessionDep,
):
    """Approve or reject a recharge request from the web app. Resolves
    through the exact same function the Telegram-side route uses, so a
    request can be handled from either channel without double-crediting —
    see RechargeRequestResolver."""
    data.validate_actionable()
    admin_id = token.credentials
    admin_username = user_service.get_username_by_id(admin_id, session)
    if admin_username is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin user not found")

    result = recharge_request_resolver.resolve(
        request_id,
        approve=(data.status.value == "approved"),
        actor_id=admin_id,
        actor_type=ActorType.ADMIN,
        resolved_by_username=admin_username,
        session=session,
    )

    if not result.ok:
        if result.reason == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recharge request not found")
        if result.reason == "already_resolved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Already resolved by {result.request.resolved_by_username}"
                if result.request and result.request.resolved_by_username
                else "This recharge request has already been resolved",
            )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    request = result.request

    # Keep the Telegram side in sync: a web-side resolution shouldn't leave
    # a stale, still-clickable Approve/Reject message sitting in the
    # targeted admin's chat.
    if request.notified_chat_id and request.notified_message_id:
        telegram_notifier.edit_message(
            request.notified_chat_id,
            request.notified_message_id,
            _resolution_text(request, admin_username),
        )

    return request
