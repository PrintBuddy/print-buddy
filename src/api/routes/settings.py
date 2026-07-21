from fastapi import APIRouter, status, HTTPException
from sqlmodel import select

from ..dependencies.token import AdminTokenDep
from ..dependencies.database import SessionDep
from ..dependencies.pagination import PaginationDep

from ...db.crud.app_config import AppConfigService
from ...db.crud.telegram_admin import TelegramAdminService
from ...db.crud.user import UserService
from ...db.models.transaction import Transaction, TransactionType
from ...db.models.refund_request import RefundRequest, RefundStatus
from ...db.models.product_purchase import ProductPurchase, ProductPurchaseStatus
from ...db.models.user import User
from ...schemas.settings import TelegramAdminRead, TelegramAdminCreate, TelegramAdminUpdate, ActivityLogEntry, TonerAlertConfig, ADConfigSchema, ADImportResultSchema, ADImportRequestSchema, ADImportPreviewSchema
from ...core.mail_assistant import send_toner_alert_email
from ...core.ldap_assistant import LDAPAssistant


router = APIRouter()
config_service = AppConfigService()
ta_service = TelegramAdminService()
user_service = UserService()
ldap_assistant = LDAPAssistant()


TONER_ALERT_KEY = "toner_alert_config"
TONER_ALERT_DEFAULT = {"enabled": False, "interval_hours": 24}
AD_CONFIG_KEY = "ad_config"
AD_CONFIG_DEFAULT = {"enabled": False, "institution_name": "", "server": "", "domain": "", "base_dn": ""}


# ─── AD Config ────────────────────────────────────────────────────────────────

@router.get(
    "/ad-config",
    response_model=ADConfigSchema,
    status_code=status.HTTP_200_OK
)
def get_ad_config(
    token: AdminTokenDep,
    session: SessionDep
):
    data = config_service.get(AD_CONFIG_KEY, session)
    return ADConfigSchema(**(data or AD_CONFIG_DEFAULT))


@router.put(
    "/ad-config",
    response_model=ADConfigSchema,
    status_code=status.HTTP_200_OK
)
def update_ad_config(
    body: ADConfigSchema,
    token: AdminTokenDep,
    session: SessionDep
):
    config_service.set(AD_CONFIG_KEY, body.model_dump(), session)
    return body


@router.post(
    "/ad-config/preview-import-users",
    response_model=ADImportPreviewSchema,
    status_code=status.HTTP_200_OK
)
def preview_ad_import_users(
    body: ADImportRequestSchema,
    token: AdminTokenDep,
    session: SessionDep
):
    ad_config = config_service.get(AD_CONFIG_KEY, session)
    if not ad_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AD config not found"
        )

    if not ad_config.get("enabled", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AD is disabled"
        )

    server = ad_config.get("server")
    domain = ad_config.get("domain")
    base_dn = ad_config.get("base_dn")
    if not server or not domain or not base_dn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AD config is incomplete"
        )

    ldap_assistant.configure(server, domain, base_dn)
    result = ldap_assistant.preview_import_users(body.username, body.pwd, session)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid AD credentials or directory search not permitted for this AD account"
        )

    return ADImportPreviewSchema(**result)


@router.post(
    "/ad-config/import-users",
    response_model=ADImportResultSchema,
    status_code=status.HTTP_200_OK
)
def import_ad_users(
    body: ADImportRequestSchema,
    token: AdminTokenDep,
    session: SessionDep
):
    ad_config = config_service.get(AD_CONFIG_KEY, session)
    if not ad_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AD config not found"
        )

    if not ad_config.get("enabled", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AD is disabled"
        )

    server = ad_config.get("server")
    domain = ad_config.get("domain")
    base_dn = ad_config.get("base_dn")
    if not server or not domain or not base_dn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AD config is incomplete"
        )

    ldap_assistant.configure(server, domain, base_dn)
    result = ldap_assistant.import_users(body.username, body.pwd, session)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid AD credentials or directory search not permitted for this AD account"
        )

    return ADImportResultSchema(**result)


# ─── Recharge Info ─────────────────────────────────────────────────────────────

# ─── Toner Alert Config ────────────────────────────────────────────────────────

@router.get(
    "/toner-alert",
    response_model=TonerAlertConfig,
    status_code=status.HTTP_200_OK
)
def get_toner_alert_config(
    token: AdminTokenDep,
    session: SessionDep
):
    data = config_service.get(TONER_ALERT_KEY, session)
    return TonerAlertConfig(**(data or TONER_ALERT_DEFAULT))


@router.put(
    "/toner-alert",
    response_model=TonerAlertConfig,
    status_code=status.HTTP_200_OK
)
def update_toner_alert_config(
    body: TonerAlertConfig,
    token: AdminTokenDep,
    session: SessionDep
):
    config_service.set(TONER_ALERT_KEY, body.model_dump(), session)
    return body


@router.post(
    "/toner-alert/test",
    status_code=status.HTTP_200_OK
)
async def test_toner_alert(
    token: AdminTokenDep,
    session: SessionDep
):
    """Sends a test low-toner alert email to all admin accounts using fake data."""
    admin_emails = user_service.get_admin_emails(session)
    if not admin_emails:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active admin accounts found to send the test email to."
        )

    mock_alerts = [
        {
            "printer_name": "Stampanti-Colori",
            "markers": [
                {"name": "C",  "level": 8,  "low_level": 10},
                {"name": "M",  "level": 7,  "low_level": 10},
                {"name": "Y",  "level": 9,  "low_level": 10},
            ],
        },
        {
            "printer_name": "Archi-Printer",
            "markers": [
                {"name": "Black", "level": 6, "low_level": 10},
            ],
        },
    ]

    await send_toner_alert_email(admin_emails, mock_alerts)
    return {"detail": f"Test alert sent to {len(admin_emails)} admin(s)."}


# ─── Telegram Admins ───────────────────────────────────────────────────────────

def _to_telegram_admin_read(ta, user) -> TelegramAdminRead:
    return TelegramAdminRead(
        id=str(ta.id),
        telegram_id=ta.telegram_id,
        user_id=str(ta.user_id),
        username=user.username if user else None,
        name=user.name if user else None,
        surname=user.surname if user else None,
        phone_number=ta.phone_number,
        accepts_transfer=ta.accepts_transfer,
        bank_name=ta.bank_name,
        bank_iban=ta.bank_iban,
        bank_link=ta.bank_link,
    )


@router.get(
    "/telegram-admins",
    response_model=list[TelegramAdminRead],
    status_code=status.HTTP_200_OK
)
def list_telegram_admins(
    token: AdminTokenDep,
    session: SessionDep,
    pagination: PaginationDep
):
    admins = ta_service.get_all(session, pagination.limit, pagination.offset)
    return [
        _to_telegram_admin_read(ta, user_service.get_user_by_id(str(ta.user_id), session))
        for ta in admins
    ]


@router.post(
    "/telegram-admins",
    response_model=TelegramAdminRead,
    status_code=status.HTTP_201_CREATED
)
def add_telegram_admin(
    body: TelegramAdminCreate,
    token: AdminTokenDep,
    session: SessionDep
):
    user = user_service.get_user_by_username(body.username, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check if this telegram_id is already registered
    existing = ta_service.get_telegram_admin(body.telegram_id, session)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Telegram ID already registered")

    ta = ta_service.create_telegram_admin(
        str(user.id), body.telegram_id, session,
        phone_number=body.phone_number,
        accepts_transfer=body.accepts_transfer,
        bank_name=body.bank_name,
        bank_iban=body.bank_iban,
        bank_link=body.bank_link,
    )

    return _to_telegram_admin_read(ta, user)


@router.patch(
    "/telegram-admins/{ta_id}",
    response_model=TelegramAdminRead,
    status_code=status.HTTP_200_OK
)
def update_telegram_admin(
    ta_id: str,
    body: TelegramAdminUpdate,
    token: AdminTokenDep,
    session: SessionDep
):
    ta = ta_service.update_telegram_admin(
        ta_id, session,
        phone_number=body.phone_number,
        accepts_transfer=body.accepts_transfer,
        bank_name=body.bank_name,
        bank_iban=body.bank_iban,
        bank_link=body.bank_link,
    )
    if ta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telegram admin not found")

    user = user_service.get_user_by_id(str(ta.user_id), session)
    return _to_telegram_admin_read(ta, user)


@router.delete(
    "/telegram-admins/{ta_id}",
    status_code=status.HTTP_200_OK
)
def remove_telegram_admin(
    ta_id: str,
    token: AdminTokenDep,
    session: SessionDep
):
    ta = ta_service.delete_by_id(ta_id, session)
    if ta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telegram admin not found")
    return {"success": True}


# ─── Activity Log ──────────────────────────────────────────────────────────────

@router.get(
    "/activity-log",
    response_model=list[ActivityLogEntry],
    status_code=status.HTTP_200_OK
)
def get_activity_log(
    token: AdminTokenDep,
    session: SessionDep,
    pagination: PaginationDep
):
    """Merged, chronological log of all admin-initiated recharges/adjustments,
    refund resolutions, and resolved (non-pending) product purchases."""
    entries: list[ActivityLogEntry] = []

    # Each source is independently ordered newest-first, so taking the top
    # (offset + limit) from each is enough to guarantee the true top
    # (offset + limit) of the merged, re-sorted result — a standard
    # k-way-merge bound — without scanning either table in full.
    fetch_cap = pagination.offset + pagination.limit

    # ── Admin-initiated transactions (RECHARGE + ADJUSTMENT) ──────────────────
    admin_tx_types = (TransactionType.RECHARGE, TransactionType.ADJUSTMENT)
    tx_stmt = (
        select(Transaction, User)
        .join(User, Transaction.user_id == User.id)   # type: ignore
        .where(Transaction.type.in_(admin_tx_types))  # type: ignore
        .where(Transaction.note.isnot(None))           # type: ignore
        .where(Transaction.note != "")                 # type: ignore
        .order_by(Transaction.created_at.desc())       # type: ignore
        .limit(fetch_cap)
    )
    for tx, target_user in session.exec(tx_stmt).all():
        # Parse "Recharge made by admin" or "Adjusted by admin"
        note = tx.note or ""
        admin_username = note.split(" by ")[-1].strip() if " by " in note else None
        entries.append(ActivityLogEntry(
            id=str(tx.id),
            action=tx.type.value,
            admin_username=admin_username,
            target_username=target_user.username,
            amount=tx.amount,
            balance_after=tx.balance_after,
            note=note,
            created_at=tx.created_at,
        ))

    # ── Resolved refunds ──────────────────────────────────────────────────────
    ref_stmt = (
        select(RefundRequest, User)
        .join(User, RefundRequest.user_id == User.id)  # type: ignore
        .where(RefundRequest.status != RefundStatus.PENDING)
        .order_by(RefundRequest.updated_at.desc())  # type: ignore
        .limit(fetch_cap)
    )
    for refund, target_user in session.exec(ref_stmt).all():
        action = (
            "refund_approved" if refund.status == RefundStatus.APPROVED
            else "refund_denied"
        )
        entries.append(ActivityLogEntry(
            id=str(refund.id),
            action=action,
            admin_username=refund.resolved_by_username,
            target_username=target_user.username,
            amount=None,
            balance_after=None,
            note=refund.admin_message,
            created_at=refund.updated_at,
        ))

    # ── Resolved product purchases ─────────────────────────────────────────────
    purchase_stmt = (
        select(ProductPurchase, User)
        .join(User, ProductPurchase.user_id == User.id)  # type: ignore
        .where(ProductPurchase.status != ProductPurchaseStatus.PENDING)
        .order_by(ProductPurchase.updated_at.desc())  # type: ignore
        .limit(fetch_cap)
    )
    for purchase, target_user in session.exec(purchase_stmt).all():
        action = (
            "purchase_fulfilled" if purchase.status == ProductPurchaseStatus.FULFILLED
            else "purchase_rejected"
        )
        note = f"{purchase.quantity}x {purchase.product_name}"
        if purchase.admin_message:
            note += f' — "{purchase.admin_message}"'
        entries.append(ActivityLogEntry(
            id=str(purchase.id),
            action=action,
            admin_username=purchase.resolved_by_username,
            target_username=target_user.username,
            amount=None,
            balance_after=None,
            note=note,
            created_at=purchase.updated_at,
        ))

    # Sort all entries newest-first, then apply the actual page window
    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries[pagination.offset:pagination.offset + pagination.limit]
